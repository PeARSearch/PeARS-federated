# SPDX-FileCopyrightText: 2022 PeARS Project, <community@pearsproject.org>, 
#
# SPDX-License-Identifier: AGPL-3.0-only

# Import flask dependencies
import re
import logging
import joblib
import numpy as np
from shutil import copyfile
from scipy import sparse
from pandas import read_csv
from math import ceil, isnan
from flask import Blueprint, flash, request, render_template, Response, stream_with_context, url_for
from flask_login import login_required, current_user
from app.auth.decorators import check_is_confirmed
from app import VEC_SIZE, LANG, OWN_BRAND
from app.api.models import Urls
from app.indexer.neighbours import neighbour_urls
from app.indexer import mk_page_vector, spider
from app.utils import readDocs, readUrls, readBookmarks, parse_query, init_pod, init_podsum
from app.utils_db import create_or_update_pod
from app.indexer.access import request_url
from app.indexer.posix import posix_doc
from os.path import dirname, join, realpath, isfile
from app.forms import IndexerForm, ManualEntryForm

app_dir_path = dirname(dirname(realpath(__file__)))
suggestions_dir_path = join(app_dir_path,'static', 'userdata')

# Define the blueprint:
indexer = Blueprint('indexer', __name__, url_prefix='/indexer')

@indexer.context_processor
def inject_brand():
    return dict(own_brand=OWN_BRAND)


# Set the route and accepted methods
@indexer.route("/", methods=["GET", "POST"])
@login_required
@check_is_confirmed
def index():
    num_db_entries = len(Urls.query.all())
    form1 = IndexerForm(request.form)
    form2 = ManualEntryForm(request.form)
    if request.method == "GET":
        return render_template("indexer/index.html", num_entries=num_db_entries, form1=form1, form2=form2)


'''
 Controllers for various ways to index
 (from file, from url, from crawl)
'''


@indexer.route("/manual", methods=["POST"])
@login_required
@check_is_confirmed
def manual():
    print("\t>> Indexer : manual")
    if Urls.query.count() == 0:
        init_podsum()
   
    form = ManualEntryForm(request.form)
    if form.validate_on_submit():
        title = request.form.get('title')
        snippet = request.form.get('description')
        u = url_for('search.index',q=' '.join(snippet.split()[:4]))
        contributor = current_user.username
        trigger = ''
        keyword = 'Tips'
        print(u, keyword, LANG, trigger, contributor)
        print("\t>> Indexer : manual_progress_file")
        messages = manual_progress_file(u, title, snippet, keyword, LANG, trigger, contributor)
        return render_template('indexer/progress_file.html', messages=messages)
    else:
        return render_template('indexer/index.html', form1=IndexerForm(request.form), form2=form)


@indexer.route("/from_url", methods=["POST"])
@login_required
@check_is_confirmed
def from_url():
    print("\t>> Indexer : from_url")
    if Urls.query.count() == 0:
        init_podsum()

    form = IndexerForm(request.form)
    if form.validate_on_submit():
        contributor = current_user.username
        user_url_file = join(suggestions_dir_path, contributor+".suggestions")
        f = open(user_url_file, 'w') #Every contributor gets their own file to avoid race conditions
        url = request.form.get('url')
        theme = request.form.get('theme')
        trigger = request.form.get('trigger')
        theme, _, lang = parse_query(theme)
        if trigger is None:
            trigger = ''
        print(url, theme, lang, trigger, contributor)
        f.write(url + ";" + theme + ";" + lang + ";" + trigger + ";" + contributor + "\n")
        f.close()
        print("\t>> Indexer : progress_file")
        messages = progress_file(contributor, user_url_file)
        return render_template('indexer/progress_file.html', messages = messages)
    else:
        return render_template('indexer/index.html', form1=form, form2=ManualEntryForm(request.form))



'''
Controllers for progress pages.
One controller per ways to index (file, crawl).
The URL indexing uses same progress as file.
'''


def progress_file(contributor, user_url_file):
    print(">> INDEXER: Running progress file")
    messages = []
    urls, themes, langs, triggers, contributors, errors = readUrls(user_url_file)
    if errors:
        return errors
    if not urls or not themes or not langs:
        messages.append('ERROR: Invalid file format.')
        return messages
    theme = themes[0]
    init_pod(contributor, theme)
    for url, theme, lang, trigger, contributor in zip(urls, themes, langs, triggers, contributors):
        access, req, request_errors = request_url(url)
        if access:
            try:
                url_type = req.headers['Content-Type']
            except:
                messages.append('ERROR: Content type could not be retrieved from header.')
                continue
            success, podsum, text, doc_id, mgs = mk_page_vector.compute_vectors(url, theme, lang, trigger, contributor, url_type)
            if success:
                posix_doc(text, doc_id, contributor, theme)
                create_or_update_pod(contributor, theme, lang, podsum)
                success_message = url+" was successfully indexed."
                messages.append(success_message)
            else:
                messages.extend(mgs)
        else:
            messages.extend(request_errors)
    return messages


def manual_progress_file(url, title, doc, theme, lang, trigger, contributor):
    print(">> INDEXER: Running manual progress file")
    init_pod(contributor, theme)
    messages = []
    doctype = 'doc'
    success, podsum, text, doc_id, mgs = mk_page_vector.compute_vectors_local_docs(url, doctype, title, doc, theme, lang, trigger, contributor)
    if success:
        posix_doc(text, doc_id, contributor, theme)
        create_or_update_pod(contributor, theme, lang, podsum)
        success_message = url+" was successfully indexed."
        messages.append(success_message)
    else:
        messages.extend(mgs)
        messages.append("ERROR: failed in index manual document. Contact your administrator.")
    return messages





######## FROM PeARS LITE #################


@indexer.route("/from_file", methods=["POST"])
@login_required
@check_is_confirmed
def from_file():
    if Urls.query.count() == 0:
        init_podsum()

    print("FILE:", request.files['file_source'])
    if request.files['file_source'].filename[-4:] == ".txt":
        file = request.files['file_source']
        # filename = secure_filename(file.filename)
        file.save(join(dir_path, "urls_to_index.txt"))
        messages = progress_file()
        return render_template('indexer/progress_file.html', messages = messages)


@indexer.route("/from_bookmarks", methods=["POST"])
@login_required
@check_is_confirmed
def from_bookmarks():
    if Urls.query.count() == 0:
        init_podsum()

    print("FILE:", request.files['file_source'])
    if "bookmarks" in request.files['file_source'].filename:
        keyword = request.form['bookmark_keyword']
        keyword, _, lang = parse_query(keyword)
        file = request.files['file_source']
        file.save(join(dir_path, "bookmarks.html"))
        urls = readBookmarks(join(dir_path,"bookmarks.html"), keyword)
        print(urls)
        f = open(join(dir_path, "urls_to_index.txt"), 'w')
        for u in urls:
            f.write(u + ";" + keyword + ";" + lang +"\n")
        f.close()
        messages = progress_file()
        return render_template('indexer/progress_file.html', messages = messages)

@indexer.route("/from_docs", methods=["POST"])
@login_required
@check_is_confirmed
def from_docs():
    if Urls.query.count() == 0:
        init_podsum()

    filename = request.files['file_source'].filename
    print("DOC FILE:", filename)
    if filename[-4:] == ".txt":
        keyword = request.form['docs_keyword']
        doctype = request.form['docs_type']
        if doctype == '' or doctype.isspace():
            doctype = 'doc'
        else:
            doctype = request.form['docs_type'].lower()
        keyword, _, lang = parse_query(keyword)
        print("LANGUAGE:",lang)
        file = request.files['file_source']
        file.save(join(dir_path, "docs_to_index.txt"))
        f = open(join(dir_path, "file_source_info.txt"), 'w')
        f.write(filename+'::'+keyword+'::'+lang+'::'+doctype+'\n')
        f.close()
        return render_template('indexer/progress_docs.html')


@indexer.route("/from_csv", methods=["POST"])
@login_required
@check_is_confirmed
def from_csv():
    if Urls.query.count() == 0:
        init_podsum()

    filename = request.files['file_source'].filename
    print("CSV FILE:", filename)
    if filename[-4:] == ".csv":
        keyword = request.form['csv_keyword']
        doctype = request.form['docs_type']
        if doctype == '' or doctype.isspace():
            doctype = 'csv'
        else:
            doctype = request.form['docs_type'].lower()
        keyword, _, lang = parse_query(keyword)
        print("LANGUAGE:",lang)
        file = request.files['file_source']
        file.save(join(dir_path, "static/userdata/csv/spreadsheet_to_index.csv"))
        copyfile(join(dir_path, "static/userdata/csv/spreadsheet_to_index.csv"), join(dir_path, "static/userdata/csv",filename))
        f = open(join(dir_path, "file_source_info.txt"), 'w')
        f.write(filename+'::'+keyword+'::'+lang+'::'+doctype+'\n')
        f.close()
        return render_template('indexer/progress_csv.html')


@indexer.route("/progress_docs")
@login_required
@check_is_confirmed
def progress_docs():
    logging.debug("Running progress local file")
    def generate():
        theme = ''
        lang = LANG
        doctype = 'doc'
        docfile = join(dir_path, "docs_to_index.txt")
        urls = readDocs(docfile)
        f = open(join(dir_path, "file_source_info.txt"), 'r')
        for line in f:
            source, theme, lang, doctype = line.rstrip('\n').split('::')
        init_pod(theme)
        c = 0
        #for url, title, snippet in zip(urls, titles, snippets):
        with open(docfile) as df:
            for l in df:
                l=l.rstrip('\n')
                if l[:4] == "<doc":
                    m = re.search('url=\"([^\"]*)\"',l)
                    url = m.group(1)
                    m = re.search('title=\"([^\"]*)\"',l)
                    title = m.group(1)
                    doc = ""
                elif "</doc" not in l:
                    doc+=l+' '
                else:
                    success, podsum, text, doc_id = mk_page_vector.compute_vectors_local_docs(url, doctype, title, doc, theme, lang)
                    if success:
                        posix_doc(text, doc_id, theme)
                        create_or_update_pod(contributor, theme, lang, podsum)
                    c += 1
                    data = ceil(c / len(urls) * 100)
                    yield "data:" + str(data) + "\n\n"

    return Response(generate(), mimetype='text/event-stream')


@indexer.route("/progress_csv")
@login_required
@check_is_confirmed
def progress_csv():
    logging.debug("Running progress local csv")
    def generate():
        theme = ''
        lang = LANG
        doctype = 'csv'
        try:
            df = read_csv(join(dir_path, "static/userdata/csv/spreadsheet_to_index.csv"), delimiter=';', encoding="utf-8")
        except:
            print("CSV Encoding is not utf-8")
            df = read_csv(join(dir_path, "static/userdata/csv/spreadsheet_to_index.csv"), delimiter=';', encoding="iso-8859-1")

        f = open(join(dir_path, "file_source_info.txt"), 'r')
        for line in f:
            source, theme, lang, doctype = line.rstrip('\n').split('::')
        init_pod(theme)
        c = 0
        columns = list(df.columns)
        table = df.to_numpy()
        for i in range(table.shape[0]):
            row = table[i]
            print(row, type(row[0]))
            if isinstance(row[0],float) and isnan(row[0]):
                continue
            title = source.replace('.csv','').title()+': '+str(row[0])+' ['+str(i)+']'
            url = source+'#'+title
            snippet = ''
            for i in range(len(columns)):
                value = str(row[i]).replace('/',' / ')
                snippet+=str(columns[i])+': ' +value+'. '
            print(url,title)
            success, podsum, text, doc_id = mk_page_vector.compute_vectors_local_docs(url, doctype, title, snippet, theme, lang)
            if success:
                posix_doc(text, doc_id, theme)
                create_or_update_pod(contributor, theme, lang, podsum)
            c += 1
            data = ceil(c / table.shape[0] * 100)
            yield "data:" + str(data) + "\n\n"

    return Response(generate(), mimetype='text/event-stream')

