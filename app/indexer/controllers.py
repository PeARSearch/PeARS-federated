# SPDX-FileCopyrightText: 2024 PeARS Project, <community@pearsproject.org>,
#
# SPDX-License-Identifier: AGPL-3.0-only

import logging
from os import getenv
from os.path import dirname, join, realpath
from time import sleep
import itertools
import hashlib
import numpy as np
from flask import session, Blueprint, request, render_template, url_for, flash, redirect, jsonify
from flask_login import login_required, current_user
from flask_babel import gettext
from langdetect import detect
from app.auth.captcha import mk_captcha, check_captcha
from app.auth.decorators import check_permissions
from app import app, db
from app.api.models import Urls, Pods, Suggestions, RejectedSuggestions
from app.indexer import mk_page_vector
from app.utils import read_urls, parse_query
from app.utils_db import create_pod_in_db, create_pod_npz_pos, create_or_replace_url_in_db, delete_url_representations, create_suggestion_in_db
from app.indexer.access import request_url
from app.indexer.posix import posix_doc
from app.forms import IndexerForm, ManualEntryForm, SuggestionForm

app_dir_path = dirname(dirname(realpath(__file__)))

# Define the blueprint:
indexer = Blueprint('indexer', __name__, url_prefix='/indexer')


@indexer.route("/", methods=["GET"])
@check_permissions(login=True, confirmed=True, admin=True)
def index():
    """Displays the indexer page.
    Computes and returns the total number
    of URLs in the entire instance. Passes
    online and offline suggestion forms to
    the indexer template.
    """
    num_db_entries = len(Urls.query.all())
    form1 = IndexerForm(request.form)
    form2 = ManualEntryForm(request.form)
    pods = Pods.query.all()
    themes = list(set([p.name.split('.u.')[0] for p in pods]))
    default_screen = 'url'
    return render_template("indexer/index.html", \
            num_entries=num_db_entries, form1=form1, form2=form2, themes=themes, default_screen=default_screen)

@indexer.route("/suggest", methods=["GET"])
def suggest():
    """Suggests a URL without indexing.
    """
    # generate captcha (public code/private string pair)
    captcha_id, captcha_correct_answer = mk_captcha()

    form = SuggestionForm()
    form.captcha_id.data = captcha_id
    pods = Pods.query.all()
    themes = list(set([p.name.split('.u.')[0] for p in pods]))
    return render_template("indexer/suggest.html", form=form, themes=themes)

@indexer.route("/amend", methods=["GET"])
@check_permissions(login=True, confirmed=True, admin=True)
def correct_entry():
    """Redisplays the indexer page when the
    user wishes to change their entry.
    """
    num_db_entries = len(Urls.query.all())
    form1 = IndexerForm(request.form)
    form2 = ManualEntryForm(request.form)
    pods = Pods.query.all()
    themes = list(set([p.name.split('.u.')[0] for p in pods]))
    default_screen = "url"
    
    if not session['index_url']:
        flash(gettext("Nothing to amend."))
        return render_template("indexer/index.html", \
            num_entries=num_db_entries, form1=form1, form2=form2, themes=themes)

    url = session['index_url']
    delete_url_representations(url)
    if 'index_description' in session:
        form2.title.data = session['index_title']
        form2.related_url.data = session['index_url']
        form2.description.data = session['index_description']
        default_screen = "manual"
        session.pop('index_description')
    else:
        form1.url.data = url
        form1.theme.data = session['index_theme']
        if session['index_note']:
            form1.theme.data = session['index_note']
    return render_template("indexer/index.html", \
            num_entries=num_db_entries, form1=form1, form2=form2, themes=themes, default_screen=default_screen)

@indexer.route("/url", methods=["POST"])
@check_permissions(login=True, confirmed=True, admin=True)
def index_from_url():
    """ Route for URL entry form.
    This is to index a URL that the user
    has suggested through the IndexerForm.
    Validates the suggestion form and calls the
    indexer (progres_file).
    """
    print("\t>> Indexer : from_url")
    contributor = current_user.username
    pods = Pods.query.all()
    themes = list(set([p.name.split('.u.')[0] for p in pods]))
    default_screen = "url"

    form = IndexerForm(request.form)
    if form.validate_on_submit():
        url = request.form.get('suggested_url').strip()
        theme = request.form.get('theme').strip()
        note = request.form.get('note').strip()
        session['index_url'] = url
        session['index_theme'] = theme
        session['index_note'] = note
        if note is None:
            note = ''
        logging.debug(f"INDEXING URL: {url} THEME: {theme} NOTE: {note} CONTRIBUTOR: {contributor}")
        success, messages, share_url = run_indexer_url(url, theme, note, contributor, request.host_url)
        if success:
            return render_template('indexer/success.html', messages=messages, share_url=share_url, url=url, theme=theme, note=note)
        return render_template('indexer/fail.html', messages = messages)
    return render_template('indexer/index.html', form1=form, form2=ManualEntryForm(request.form), themes=themes, default_screen=default_screen)

@indexer.route("/manual", methods=["POST"])
@check_permissions(login=True, confirmed=True, admin=True)
def index_from_manual():
    """ Route for manual (offline) entry form.
    This is to index offline tips that the user
    may want to share on the instance.
    Validates the ManualEntryForm and calls the
    indexer (manual_progres_file).
    """
    print("\t>> Indexer : manual")
    contributor = current_user.username
    pods = Pods.query.all()
    themes = list(set([p.name.split('.u.')[0] for p in pods]))
    default_screen = "manual"

    form = ManualEntryForm(request.form)
    if form.validate_on_submit():
        title = request.form.get('title').strip()
        snippet = request.form.get('description').strip()
        url = request.form.get('related_url').strip()
        print("MANUAL URL",url)
        lang = detect(snippet)
        # Hack if language of contribution is not recognized
        if lang not in app.config['LANGS']:
            lang = app.config['LANGS'][0]
        if not url:
            h = hashlib.new('sha256')
            h.update(snippet.encode())
            url = 'pearslocal'+h.hexdigest()
        theme = 'Tips'
        note = ''
        session['index_url'] = url
        session['index_title'] = title
        session['index_description'] = snippet
        success, messages, share_url = run_indexer_manual(url, title, snippet, theme, lang, note, contributor, request.host_url)
        if success:
            return render_template('indexer/success.html', messages=messages, share_url=share_url,  theme=theme, note=snippet)
        return render_template('indexer/fail.html', messages = messages)
    return render_template('indexer/index.html', form1=IndexerForm(request.form), form2=form, themes=themes, default_screen=default_screen)

@indexer.route("/suggestion", methods=["POST"])
def run_suggest_url():
    """ Save the suggested URL in waiting list.
    """
    print(">> INDEXER: run_suggest_url: Save suggested URL.")
    form = SuggestionForm(request.form)
    if form.validate_on_submit():
        url = request.form.get('suggested_url').strip()
        theme = request.form.get('theme').strip()
        note = request.form.get('note').strip()
        captcha_id = request.form.get('captcha_id')
        captcha_user_answer = request.form.get('captcha_answer')
        if current_user.is_authenticated:
            contributor = current_user.username
        else:
            contributor = 'anonymous'
        
        if not check_captcha(captcha_id, captcha_user_answer):
            flash(gettext('The captcha was incorrectly answered.'))
            captcha_id, captcha_correct_answer = mk_captcha()
            form = SuggestionForm()
            form.suggested_url.data = request.form.get('suggested_url').strip()
            form.theme.data = request.form.get('theme').strip()
            form.note.data = request.form.get('note').strip()
            form.captcha_answer.data = ""
            form.captcha_id.data = captcha_id
            pods = Pods.query.all()
            themes = list(set([p.name.split('.u.')[0] for p in pods]))
            return render_template('indexer/suggest.html', form=form, themes=themes)

        print(url, theme, note)
        create_suggestion_in_db(url=url, pod=theme, notes=note, contributor=contributor)
        flash(gettext('Many thanks for your suggestion'))
        return redirect(url_for('indexer.suggest'))
    print("FORM ERRORS:", form.errors)
    # generate captcha (public code/private string pair)
    captcha_id, captcha_correct_answer = mk_captcha()
    form.captcha_id.data = captcha_id
    pods = Pods.query.all()
    themes = list(set([p.name.split('.u.')[0] for p in pods]))
    return render_template('indexer/suggest.html', form=form, themes=themes)

@indexer.route("/index_from_suggestion_ajax", methods=["POST"])
@check_permissions(login=True, confirmed=True, admin=True)
def index_url_ajax():
    url = request.json.get('url').strip()
    theme = request.json.get('theme').strip()
    notes = request.json.get('notes').strip()

    if not theme:
        return jsonify({
            "success": False,
            "messages": ["Pod name cannot be empty"]
        })

    custom_theme = request.json.get('customTheme', 'n') == 'y'
    existing_url = (
        db.session
        .query(Urls)
        .filter_by(url=url)
        .first()
    )
    if existing_url:
        return jsonify({
            "success": False,
            "messages": [f"url {url} already exists (pod={existing_url.pod}, contributor={existing_url.contributor})"] 
        })
    
    if custom_theme: # custom pod chosen by admin
        suggestion = (
            db.session
            .query(Suggestions)
            .filter_by(url=url)
            .order_by(Suggestions.date_created.desc())
            .first()
        )
    else:  # pod was chosen from the list of suggested themes 
        suggestion = (
            db.session
            .query(Suggestions)
            .filter_by(url=url, pod=theme)
            .order_by(Suggestions.date_created.desc())
            .first()
        )
    
    if not suggestion:
        return jsonify ({
            "success": False,
            "messages": [f"could not find suggestion with url {url}"]
        })

    s_success, s_messages, _ = run_indexer_url(url, theme, notes, current_user.username, request.host_url)
    return jsonify({
        "success": s_success, 
        "messages": s_messages
    })


@indexer.route("/reject_suggestion_ajax", methods=["POST"])
@check_permissions(login=True, confirmed=True, admin=True)
def reject_suggestion_ajax():
    url = request.json.get  ('url').strip()
    reason = request.json.get('reason').strip()
    matching_suggestions = (
        db.session
        .query(Suggestions)
        .filter_by(url=url)
        .all()
    )
    if not matching_suggestions:
        return jsonify({
            "success": False,
            "messages": [f"url {url} does not exist in the suggestion database"]
        })

    # record rejected suggestion
    rs_ids = []
    for s in matching_suggestions:
        rs = RejectedSuggestions(url=url, pod=s.pod, notes=s.notes, contributor=s.contributor, rejection_reason=reason)
        rs_ids.append(rs_ids)
        db.session.add(rs)

        # remove original suggestion from DB
        db.session.delete(s)

        # commit changes
        db.session.commit()

    return jsonify({
        "success": True,
        "messages": [f"Created entries in RejectedSuggestions with ids {rs_ids}"]
    })


@indexer.route("/index_suggestions", methods=["GET", "POST"])
@check_permissions(login=True, confirmed=True, admin=True)
def index_suggestions():
    hide_already_indexed_urls = request.args.get("hide_already_indexed", "y") == "y"

    suggestions = (
        db.session
        .query(Suggestions)
        .order_by(Suggestions.url, Suggestions.date_created.desc())
    )

    # use python itertools for grouping/summarizing because it's more flexible
    grouped_by_url = itertools.groupby(suggestions, lambda s: s.url)
    suggestions_summary = []
    for url, suggestions_with_url in grouped_by_url:
        
        # check if this URL was already indexed
        existing_urls = (
            db.session
            .query(Urls)
            .filter_by(url=url)
            .all()
        )
        if existing_urls and hide_already_indexed_urls:
            continue
        
        total_count = 0
        pod_counts = {}
        created_dates = []
        notes = []
        grouped_by_pod = itertools.groupby(suggestions_with_url, lambda s: s.pod)
        for pod, suggestions_with_pod in grouped_by_pod:
            suggestion_list = list(suggestions_with_pod)
            created_dates.extend([s.date_created for s in suggestion_list])
            notes.extend([s.notes for s in suggestion_list])
            pod_count = len(suggestion_list)
            pod_counts[pod] = pod_count
            total_count += pod_count
        sort_by_date_idx = np.argsort(created_dates)
        created_dates_sorted = np.array(created_dates)[sort_by_date_idx]
        notes_sorted = np.array(notes)[sort_by_date_idx]
        notes_combined = "\n\n".join(notes_sorted)
        _notes_preview = " | ".join(notes_sorted)[:50]
        notes_preview = _notes_preview if len(_notes_preview) < 50 else _notes_preview + "..."
        suggestions_summary.append({
            "url": url, 
            "total_count": total_count, 
            "suggestions_by_pod": pod_counts, 
            "first_created": created_dates_sorted[0], 
            "last_created": created_dates_sorted[-1], 
            "notes": notes_combined,
            "notes_preview": notes_preview,
            "already_indexed_in": [u.pod for u in existing_urls]
        })

    return render_template("indexer/index_suggestions.html", suggestions=suggestions_summary, hide_already_indexed_urls=hide_already_indexed_urls)


def run_indexer_url(url, theme, note, contributor, host_url):
    """ Run the indexer over the suggested URL.
    This includes checking the robots.txt, and producing 
    representations that include entries in the positional
    index as well as vectors. A new entry is also
    added to the database.
    """
    print(">> INDEXER: run_indexer_url: Running indexer over suggested URL.")
    messages = []
    indexed = False
    share_url = ''
    access, req, request_errors = request_url(url)
    if access:
        try:
            url_type = req.headers['Content-Type']
        except:
            messages.append(gettext('ERROR: Content type could not be retrieved from header.'))
            return indexed, messages, share_url
        success, text, lang, title, snippet, idv, mgs = \
                mk_page_vector.compute_vector(url, theme, contributor, url_type)
        if success:
            create_pod_in_db(contributor, theme, lang)
            #posix_doc(text, idx, contributor, lang, theme)
            share_url = join(host_url,'api', 'get?url='+url)
            create_or_replace_url_in_db(\
                    url, title, idv, snippet, theme, lang, note, share_url, contributor, 'url')
            indexed = True
        else:
            messages.extend(mgs)
    else:
        messages.extend(request_errors)
    return indexed, messages, share_url


def run_indexer_manual(url, title, doc, theme, lang, note, contributor, host_url):
    """ Run the indexer over manually contributed information.
    
    Arguments: a url (internal and bogus, constructed by 'index_from_manual'),
    the title and content of the added document, a topic, language, note 
    information, as well as the username of the contributor.
    """
    print(">> INDEXER: run_indexer_manual: Running indexer over manually added information.")
    messages = []
    indexed = False
    create_pod_npz_pos(contributor, theme, lang)
    success, text, snippet, idv = mk_page_vector.compute_vector_local_docs(\
            title, doc, theme, lang, contributor)
    share_url = join(host_url,'api', 'get?url='+url)
    if success:
        create_pod_in_db(contributor, theme, lang)
        #posix_doc(text, idx, contributor, lang, theme)
        create_or_replace_url_in_db(url, title, idv, snippet, theme, lang, note, share_url, contributor, 'doc')
        indexed = True
    else:
        messages.append(gettext("There was a problem indexing your entry. Please check the submitted data."))
        messages.append(gettext("Your entry:"), doc)
        indexed = False
    return indexed, messages, share_url


def index_doc_from_cli(title, doc, theme, lang, contributor, url, note, host_url):
    """ Index a single doc, to be called by a CLI function."""
    u = db.session.query(Urls).filter_by(url=url).first()
    if u:
        return False #URL exists already
    create_pod_npz_pos(contributor, theme, lang)
    success, text, snippet, idv = \
            mk_page_vector.compute_vector_local_docs(title, doc, theme, lang, contributor)
    if success:
        create_pod_in_db(contributor, theme, lang)
        share_url = join(host_url,'api', 'get?url='+url)
        create_or_replace_url_in_db(\
                url, title, idv, snippet, theme, lang, note, share_url, contributor, 'url')
        return True
    else:
        return False

