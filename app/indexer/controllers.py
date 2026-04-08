# SPDX-FileCopyrightText: 2026 PeARS Project, <community@pearsproject.org>,
#
# SPDX-License-Identifier: AGPL-3.0-only

import logging
from os.path import dirname, join, realpath
from datetime import datetime
import itertools
from urllib.parse import urljoin, urlparse
import numpy as np
from flask import current_app
from flask import session, Blueprint, request, render_template, url_for, flash, redirect, jsonify
from flask_login import current_user
from flask_babel import gettext
from langdetect import detect
from markupsafe import Markup, escape
from app.auth.captcha import mk_captcha, check_captcha
from app.auth.decorators import check_permissions
from app.extensions import db
from app.api.models import Urls, Pods, Suggestions, RejectedSuggestions, Personalization
from app.indexer import mk_page_vector
from app.utils_db import create_pod_in_db, create_pod_npz_pos, create_or_replace_url_in_db, delete_url_representations, create_suggestion_in_db, check_url_exists
from app.indexer.access import request_url
from app.forms import IndexerForm, WebSourceForm, NewContentForm, SuggestionForm

app_dir_path = dirname(dirname(realpath(__file__)))

# Define the blueprint:
indexer = Blueprint('indexer', __name__, url_prefix='/indexer')
logger = logging.getLogger(__name__)


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
    form = IndexerForm(request.form)
    pods = Pods.query.all()
    themes = list(set([p.name.split('.u.')[0] for p in pods]))
    form.suggested_url.data = session.pop('index_url', '')
    form.theme.data = session.pop('index_theme', '')
    form.note.data = session.pop('index_note', '')
    return render_template("indexer/index.html", num_entries=num_db_entries, form=form, themes=themes)


@indexer.route("/write-and-index", methods=["GET"])
@check_permissions(login=True, confirmed=True, admin=True)
def write_and_index():
    """Displays the indexer page for writing content
    and indexing it on that PeARS instance.
    """
    num_db_entries = len(Urls.query.all())
    form = NewContentForm(request.form)
    pods = Pods.query.all()
    themes = list({p.name.split('.u.')[0] for p in pods})
    return render_template("indexer/write_and_index.html", num_entries=num_db_entries, form=form, themes=themes)


@indexer.route("/source", methods=["GET"])
@check_permissions(login=True, confirmed=True, admin=True)
def write_source_commentary():
    """Displays the indexer page for writing content
    and indexing it on that PeARS instance.
    """
    num_db_entries = len(Urls.query.all())
    form = WebSourceForm(request.form)
    pods = Pods.query.all()
    themes = list({p.name.split('.u.')[0] for p in pods})
    return render_template("indexer/web_commentary.html", num_entries=num_db_entries, form=form, themes=themes)


@indexer.route("/suggest", methods=["GET"])
def suggest():
    """Suggests a URL without indexing.
    """
    # generate captcha (public code/private string pair)
    captcha_id, _ = mk_captcha()
    form = SuggestionForm()
    form.captcha_id.data = captcha_id
    pods = Pods.query.all()
    themes = list({p.name.split('.u.')[0] for p in pods})
    internal_message = db.session.query(Personalization).filter_by(feature='suggestions_info').first()
    if internal_message:
        logger.debug("MSG %s", internal_message)
        internal_message = internal_message.text
    return render_template("indexer/suggest.html", form=form, themes=themes, internal_message=internal_message)


@indexer.route("/url", methods=["POST"])
@check_permissions(login=True, confirmed=True, admin=True)
def index_from_url():
    """ Route for URL entry form.
    This is to index a URL that the user
    has suggested through the IndexerForm.
    Validates the suggestion form and calls the
    indexer (progress_file).
    """
    logger.info("index_from_url")
    contributor = current_user.username
    pods = Pods.query.all()
    themes = themes = list({p.name.split('.u.')[0] for p in pods})

    form = IndexerForm(request.form)
    if form.validate_on_submit():
        url = request.form.get('suggested_url').strip()
        theme = request.form.get('theme').strip()
        note = request.form.get('note').strip()
        if note is None:
            note = ''
        logger.debug("Indexing url=%s theme=%s note=%s contributor=%s", url, theme, note, contributor)
        success, messages, share_url = run_indexer_url(url, theme, note, contributor, request.host_url)
        if success:
            return render_template('indexer/success.html', messages=messages, share_url=share_url, url=url, theme=theme, note=note)
        return render_template('indexer/fail.html', messages=messages, url=url, theme=theme, note=note, source='url')
    return render_template('indexer/index.html', form=form, themes=themes)

@indexer.route("/commentary", methods=["POST"])
@check_permissions(login=True, confirmed=True, admin=True)
def index_from_web_commentary():
    """ Route for web commentary entry form.
    """
    logger.info("index_from_manual")
    contributor = current_user.username
    pods = Pods.query.all()
    themes = list({p.name.split('.u.')[0] for p in pods})

    form = WebSourceForm(request.form)
    if form.validate_on_submit():
        title = request.form.get('title').strip()
        theme = request.form.get('theme').strip()
        content = escape(request.form.get('description').strip())
        chosen_license = request.form.get('chosen_license').strip()
        share_url = request.form.get('related_url').strip()
        url = 'comment-'+title.lower().replace(' ','-')
        c = 2
        while check_url_exists(url):
            url+=f"-{c}"
            c+=1
        logger.debug("Manual URL: %s", url)
        lang = detect(content)
        # Hack if language of contribution is not recognized
        if lang not in current_app.config['LANGS']:
            lang = current_app.config['LANGS'][0]
        success, messages, snippet = run_indexer_manual(url, title, theme, lang, share_url, content, contributor, chosen_license, request.host_url)
        if success:
            return render_template('indexer/success.html', messages=messages, share_url=share_url, theme=theme, note=snippet)
        return render_template('indexer/fail.html', messages=messages, title=title, description=snippet, url=url, source='manual')
    return render_template('indexer/web_commentary.html', form=form, themes=themes)


@indexer.route("/newcontent", methods=["POST"])
@check_permissions(login=True, confirmed=True, admin=True)
def index_from_new_content():
    """ Route for new content entry form.
    """
    logger.info("index new content")
    contributor = current_user.username
    pods = Pods.query.all()
    themes = list({p.name.split('.u.')[0] for p in pods})

    form = NewContentForm(request.form)
    if form.validate_on_submit():
        title = request.form.get('title').strip()
        theme = request.form.get('theme').strip()
        content = escape(request.form.get('content').strip())
        chosen_license = request.form.get('chosen_license').strip()
        lang = detect(content)
        # Hack if language of contribution is not recognized
        if lang not in current_app.config['LANGS']:
            lang = current_app.config['LANGS'][0]
        url = 'content-'+title.lower().replace(' ','-')
        c = 2
        while check_url_exists(url):
            url+=f"-{c}"
            c+=1
        share_url = join(request.host_url, 'api', 'show?url='+url)
        success, messages, snippet = run_indexer_manual(url, title, theme, lang, share_url, content, contributor, chosen_license, request.host_url)
        if success:
            return render_template('indexer/success.html', messages=messages, share_url=share_url,  theme=theme, note=snippet)
        return render_template('indexer/fail.html', messages = messages)
    num_db_entries = len(Urls.query.all())
    flash("There was a problem with indexing your entry.", 'danger')
    return render_template('indexer/write_and_index.html', num_entries=num_db_entries, form=form, themes=themes)


@indexer.route("/suggestion", methods=["POST"])
def run_suggest_url():
    """ Save the suggested URL in waiting list.
    """
    logger.info("run_suggest_url: Save suggested URL.")
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
            flash(gettext('The captcha was incorrectly answered.'), "danger")
            captcha_id, _ = mk_captcha()
            form = SuggestionForm()
            form.suggested_url.data = request.form.get('suggested_url').strip()
            form.theme.data = request.form.get('theme').strip()
            form.note.data = request.form.get('note').strip()
            form.captcha_answer.data = ""
            form.captcha_id.data = captcha_id
            pods = Pods.query.all()
            themes = list({p.name.split('.u.')[0] for p in pods})
            return render_template('indexer/suggest.html', form=form, themes=themes)

        logger.debug("%s %s %s", url, theme, note)
        create_suggestion_in_db(url=url, pod=theme, notes=note, contributor=contributor)
        flash(gettext('Many thanks for your suggestion'), "success")
        return redirect(url_for('indexer.suggest'))
    logger.debug("Form errors: %s", form.errors)
    # generate captcha (public code/private string pair)
    captcha_id, _ = mk_captcha()
    form.captcha_id.data = captcha_id
    pods = Pods.query.all()
    themes = list({p.name.split('.u.')[0] for p in pods})
    return render_template('indexer/suggest.html', form=form, themes=themes)


@indexer.route("/index_from_suggestion_ajax", methods=["POST"])
@check_permissions(login=True, confirmed=True, admin=True)
def index_url_ajax():
    url = request.json.get('url').strip()
    orig_url = request.json.get('origUrl').strip()
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
            .filter_by(url=orig_url)
            .order_by(Suggestions.date_created.desc())
            .first()
        )
    else:  # pod was chosen from the list of suggested themes 
        suggestion = (
            db.session
            .query(Suggestions)
            .filter_by(url=orig_url, pod=theme)
            .order_by(Suggestions.date_created.desc())
            .first()
        )
    
    if not suggestion:
        return jsonify ({
            "success": False,
            "messages": [f"could not find suggestion with original url {orig_url}"]
        })

    s_success, s_messages, _ = run_indexer_url(url, theme, notes, current_user.username, request.host_url)

    # we keep the suggestion in the DB but change the url so it matches with what we indexed  
    suggestion.url = url
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    suggestion.notes += f"\n\n-----\nTimestamp: {timestamp}\nIndexed as: {url}\nOriginal url: {orig_url}"
    db.session.add(suggestion)
    db.session.commit()

    return jsonify({
        "success": s_success, 
        "messages": s_messages
    })


@indexer.route("/reject_suggestion_ajax", methods=["POST"])
@check_permissions(login=True, confirmed=True, admin=True)
def reject_suggestion_ajax():
    url = (request.json.get('origUrl') or request.json.get('orig_url', '')).strip()
    reason = (request.json.get('reason') or '').strip()
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
            notes.extend([s.notes.strip() for s in suggestion_list if s.notes])
            pod_count = len(suggestion_list)
            pod_counts[pod] = pod_count
            total_count += pod_count
        sort_by_date_idx = np.argsort(created_dates)
        created_dates_sorted = np.array(created_dates)[sort_by_date_idx]
        notes_sorted = np.array(notes)[sort_by_date_idx] if len(notes) > 0 else []
        notes_combined = "\n\n".join(notes_sorted)
        _notes_preview = " | ".join(notes_sorted)[:50]
        notes_preview = _notes_preview if len(_notes_preview) < 50 else _notes_preview + "..."
        suggestions_summary.append({
            "url": url, 
            "cleaned_url": _clean_url(url),
            "total_count": total_count, 
            "suggestions_by_pod": pod_counts, 
            "first_created": created_dates_sorted[0], 
            "last_created": created_dates_sorted[-1], 
            "notes": notes_combined,
            "notes_preview": notes_preview,
            "already_indexed_in": [u.pod for u in existing_urls]
        })

    suggestions_sorted = sorted(suggestions_summary, key=lambda s: s["first_created"], reverse=True)
    return render_template("indexer/index_suggestions.html", suggestions=suggestions_sorted, hide_already_indexed_urls=hide_already_indexed_urls)


def _clean_url(url):
    return urljoin(url, urlparse(url).path)


def run_indexer_url(url, theme, notes, contributor, host_url):
    """ Run the indexer over the suggested URL.
    This includes checking the robots.txt, and producing 
    representations that include entries in the positional
    index as well as vectors. A new entry is also
    added to the database.
    """
    logger.info("run_indexer_url: Running indexer over suggested URL.")
    messages = []
    indexed = False
    doctype = 'url'
    share_url = ''
    content = None
    img = None
    access, req, request_errors = request_url(url)
    if access:
        try:
            url_type = req.headers['Content-Type']
        except:
            messages.append(gettext('ERROR: Content type could not be retrieved from header.'))
            return indexed, messages, share_url
        success, _, lang, title, snippet, idv, mgs = \
                mk_page_vector.compute_vector(url, theme, contributor, url_type)
        if success:
            create_pod_in_db(contributor, theme, lang)
            #posix_doc(text, idx, contributor, lang, theme)
            share_url = join(host_url,'api', 'get?url='+url)
            create_or_replace_url_in_db(url, title, snippet, doctype, idv, theme, notes, content, img, share_url, contributor)
            indexed = True
        else:
            messages.extend(mgs)
    else:
        messages.extend(request_errors)
    return indexed, messages, share_url

def run_indexer_manual(url, title, theme, lang, share_url, usercontent, contributor, chosen_license, host_url):
    """ Run the indexer over manually contributed information.
    
    Arguments: a url (internal and bogus, constructed by 'index_from_manual'),
    the title and content of the added document, a topic, language, content
    information, as well as the username of the contributor.
    """
    logger.info("run_indexer_manual: Running indexer over manually added information.")
    messages = []
    indexed = False
    doctype = 'content'
    snippet = ''
    notes = None
    img = None
    indexed = False

    create_pod_npz_pos(contributor, theme, lang)
    success, _, snippet, idv = mk_page_vector.compute_vector_local_docs(\
            title, usercontent, theme, lang, contributor)
    if success:
        create_pod_in_db(contributor, theme, lang)
        #posix_doc(text, idx, contributor, lang, theme)
        snippet = snippet.replace('\r\n', ' ')
        usercontent = usercontent.replace('\r\n', Markup('<br>'))
        create_or_replace_url_in_db(url, title, snippet, doctype, idv, theme, notes,\
                usercontent, img, share_url, contributor, url_license=chosen_license)
        indexed = True
    else:
        messages.append(gettext("There was a problem indexing your entry. Please check the submitted data."))
        messages.append(gettext("Your entry:"), usercontent)
        indexed = False
    return indexed, messages, snippet


def index_doc_from_cli(title, doc, theme, lang, contributor, url, notes, host_url):
    """ Index a single doc, to be called by a CLI function."""
    doctype='url'
    content=None
    img=None
    u = db.session.query(Urls).filter_by(url=url).first()
    if u:
        return False #URL exists already
    create_pod_npz_pos(contributor, theme, lang)
    success, text, snippet, idv = \
            mk_page_vector.compute_vector_local_docs(title, doc, theme, lang, contributor)
    if success:
        create_pod_in_db(contributor, theme, lang)
        share_url = join(host_url,'api', 'get?url='+url)
        create_or_replace_url_in_db(url, title, snippet, doctype, idv, theme, notes, content, img, share_url, contributor)
        return True
    else:
        return False

