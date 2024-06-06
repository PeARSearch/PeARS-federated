# SPDX-FileCopyrightText: 2023 PeARS Project, <community@pearsproject.org>,
#
# SPDX-License-Identifier: AGPL-3.0-only

import logging
from os import getenv
from os.path import dirname, join, realpath
from time import sleep
import hashlib
from flask import session, Blueprint, request, render_template, url_for, flash
from flask_login import login_required, current_user
from flask_babel import gettext
from langdetect import detect
from app.auth.decorators import check_is_confirmed
from app import LANGS, OWN_BRAND
from app.api.models import Urls, Pods
from app.indexer import mk_page_vector
from app.utils import read_urls, parse_query
from app.utils_db import (create_idx_to_url, create_pod_in_db, create_pod_npz_pos,
        add_to_idx_to_url, add_to_npz_to_idx, create_or_replace_url_in_db,
        delete_url_representations)
from app.indexer.access import request_url
from app.indexer.posix import posix_doc
from app.forms import IndexerForm, ManualEntryForm

app_dir_path = dirname(dirname(realpath(__file__)))
suggestions_dir_path = getenv("SUGGESTIONS_DIR", join(app_dir_path, 'userdata'))

# Define the blueprint:
indexer = Blueprint('indexer', __name__, url_prefix='/indexer')

@indexer.context_processor
def inject_brand():
    """Inject brand information into page
    (logo on all pages and info on start page.)
    """
    return dict(own_brand=OWN_BRAND)


@indexer.route("/", methods=["GET"])
@login_required
@check_is_confirmed
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


@indexer.route("/amend", methods=["GET"])
@login_required
@check_is_confirmed
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
    if url.startswith('pearslocal'):
        form2.title.data = session['index_title']
        form2.description.data = session['index_description']
        default_screen = "manual"
    else:
        form1.url.data = url
        form1.theme.data = session['index_theme']
        if session['index_note']:
            form1.theme.data = session['index_note']
    return render_template("indexer/index.html", \
            num_entries=num_db_entries, form1=form1, form2=form2, themes=themes, default_screen=default_screen)

@indexer.route("/url", methods=["POST"])
@login_required
@check_is_confirmed
def index_from_url():
    """ Route for URL entry form.
    This is to index a URL that the user
    has suggested through the IndexerForm.
    Validates the suggestion form and calls the
    indexer (progres_file).
    """
    print("\t>> Indexer : from_url")
    contributor = current_user.username
    create_idx_to_url(contributor)
    pods = Pods.query.all()
    themes = list(set([p.name.split('.u.')[0] for p in pods]))

    form = IndexerForm(request.form)
    if form.validate_on_submit():
        user_url_file = join(suggestions_dir_path, contributor+".suggestions")
        url = request.form.get('suggested_url').strip()
        theme = request.form.get('theme').strip()
        note = request.form.get('note').strip()
        session['index_url'] = url
        session['index_theme'] = theme
        session['index_note'] = note
        if note is None:
            note = ''
        logging.debug(f"INDEXING URL: {url} THEME: {theme} NOTE: {note} CONTRIBUTOR: {contributor}")
        with open(user_url_file, 'w', encoding="utf-8") as f:
            f.write(url + ";" + theme + ";" + note + ";" + contributor + "\n")
        success, messages, share_url = run_indexer_url(user_url_file, request.host_url)
        if success:
            return render_template('indexer/success.html', messages=messages, share_url=share_url, url=url, theme=theme, note=note)
        return render_template('indexer/fail.html', messages = messages)
    return render_template('indexer/index.html', form1=form, form2=ManualEntryForm(request.form), themes=themes)



@indexer.route("/manual", methods=["POST"])
@login_required
@check_is_confirmed
def index_from_manual():
    """ Route for manual (offline) entry form.
    This is to index offline tips that the user
    may want to share on the instance.
    Validates the ManualEntryForm and calls the
    indexer (manual_progres_file).
    """
    print("\t>> Indexer : manual")
    contributor = current_user.username
    create_idx_to_url(contributor)

    form = ManualEntryForm(request.form)
    if form.validate_on_submit():
        title = request.form.get('title').strip()
        snippet = request.form.get('description').strip()
        lang = detect(snippet)
        # Hack if language of contribution is not recognized
        if lang not in LANGS:
            lang = LANGS[0]
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
    return render_template('indexer/index.html', form1=IndexerForm(request.form), form2=form)



def run_indexer_url(user_url_file, host_url):
    """ Run the indexer over the suggested URL.
    This includes checking the robots.txt, and producing 
    representations that include entries in the positional
    index as well as vectors. A new entry is also
    added to the database.

    Arguments: the file containing the information provided 
    by the user about the URL to index (auto-generated by 
    'index_from_url') and the host name.
    """
    print(">> INDEXER: run_indexer_url: Running indexer over suggested URL.")
    messages = []
    indexed = False
    share_url = ''
    urls, themes, notes, contributors, errors = read_urls(user_url_file)
    if errors:
        return indexed, errors, share_url
    if not urls or not themes:
        messages.append(gettext('ERROR: Invalid file format.'))
        return indexed, messages, share_url
    for url, theme, note, contributor in zip(urls, themes, notes, contributors):
        access, req, request_errors = request_url(url)
        if access:
            try:
                url_type = req.headers['Content-Type']
            except:
                messages.append(gettext('ERROR: Content type could not be retrieved from header.'))
                continue
            idx = add_to_idx_to_url(contributor, url)
            success, text, lang, title, snippet, vid, mgs = \
                    mk_page_vector.compute_vector(url, theme, contributor, url_type)
            if success:
                create_pod_in_db(contributor, theme, lang)
                posix_doc(text, idx, contributor, lang, theme)
                add_to_npz_to_idx(theme+'.u.'+contributor, lang, vid, idx)
                share_url = host_url+"api/get?url="+url
                create_or_replace_url_in_db(\
                        url, title, snippet, theme, lang, note, share_url, contributor, 'url')
                indexed = True
            else:
                messages.extend(mgs)
        else:
            messages.extend(request_errors)
        #Only sleep if we are indexing many pages at the same time
        if url != urls[-1]:
            sleep(2)
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
    create_pod_in_db(contributor, theme, lang)
    idx = add_to_idx_to_url(contributor, url)
    success, text, snippet, vid = mk_page_vector.compute_vector_local_docs(\
            title, doc, theme, lang, contributor)
    share_url = join(host_url, url_for('api.return_specific_url')+'?url='+url)
    if success:
        posix_doc(text, idx, contributor, lang, theme)
        add_to_npz_to_idx(theme+'.u.'+contributor, lang, vid, idx)
        create_or_replace_url_in_db(url, title, snippet, theme, lang, note, share_url, contributor, 'doc')
        indexed = True
    else:
        messages.append(gettext("There was a problem indexing your entry. Please check the submitted data."))
        messages.append(gettext("Your entry:"), doc)
        indexed = False
    return indexed, messages, share_url


def index_doc_from_cli(title, doc, theme, lang, contributor, url, note, host_url):
    """ Index a single doc, to be called by a CLI function."""
    create_idx_to_url(contributor)
    create_pod_npz_pos(contributor, theme, lang)
    create_pod_in_db(contributor, theme, lang)
    idx = add_to_idx_to_url(contributor, url)
    success, text, snippet, vid = \
            mk_page_vector.compute_vector_local_docs(title, doc, theme, lang, contributor)
    if success:
        create_pod_in_db(contributor, theme, lang)
        posix_doc(text, idx, contributor, lang, theme)
        add_to_npz_to_idx(theme+'.u.'+contributor, lang, vid, idx)
        share_url = host_url+"api/get?url="+url
        create_or_replace_url_in_db(\
                url, title, snippet, theme, lang, note, share_url, contributor, 'url')
        return True
    else:
        return False

