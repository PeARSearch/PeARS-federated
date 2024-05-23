# SPDX-FileCopyrightText: 2024 PeARS Project, <community@pearsproject.org>, 
#
# SPDX-License-Identifier: AGPL-3.0-only

import logging
from os import getenv
from os.path import dirname, join, realpath
from glob import glob
import numpy as np
from random import shuffle
from markupsafe import Markup
from flask import Blueprint, request, render_template, flash, url_for, redirect
from flask_login import current_user
from flask_babel import gettext
from app.search import score_pages
from app.utils import parse_query, beautify_title, beautify_snippet
from app import app, models, db
from app import LANGS, OWN_BRAND

# Define the blueprint:
search = Blueprint('search', __name__, url_prefix='')

dir_path = dirname(dirname(dirname(realpath(__file__))))
static_dir = join(dir_path,'app','static')
pod_dir = getenv("PODS_DIR", join('app','pods'))


@search.context_processor
def inject_brand():
    """Inject brand information into page
    (logo on all pages and info on start page.)
    """
    return dict(own_brand=OWN_BRAND)

@search.route('/')
def index():
    """ Route for the main search page.
    """
    results = []
    internal_message = ""
    query = request.args.get('q')
    if query:
        query = query.strip()
    
    if not query:
        placeholder = app.config['SEARCH_PLACEHOLDER']
        if current_user.is_authenticated and not current_user.is_confirmed:
            message = Markup(gettext("You have not confirmed your account.<br>\
                    Please use the link in the email that was sent to you, \
                    or request a new link by clicking <a href='../auth/resend'>here</a>."))
            flash(message)
        if OWN_BRAND:
            with open(join(static_dir,'intro.txt'), 'r', encoding="utf-8") as f:
                internal_message = f.read().replace('\n', '<br>')
        return render_template("search/index.html", internal_message=internal_message, \
                own_brand=OWN_BRAND, placeholder=placeholder)
    
    with open(join(static_dir,'did_you_know.txt'), 'r', encoding="utf-8") as f:
        messages = f.read().splitlines()
        shuffle(messages)
        internal_message = messages[0]
   
    results = get_search_results(query)
    displayresults = prepare_gui_results(query, results)
    return render_template('search/results.html', query=query, results=displayresults, \
            internal_message=internal_message, own_brand=OWN_BRAND)


def prepare_gui_results(query, results):
    if results is None or len(results) == 0:
        return None
    displayresults = []
    for url, r in results.items():
        r['title'] = r['title'][:70]
        r['snippet'] = beautify_snippet(r['snippet'], r['img'], query)
        logging.debug(f"RESULT URL {url}")
        if 'url=pearslocal' not in url:
            r['snippet'] = ' '.join(r['snippet'].split()[:10]) #10 to conform with EU regulations
        if r['notes'] == 'None':
            r['notes'] = None
        else:
            r['notes'] = r['notes'].split('<br>')
        values = list(r.values())
        displayresults.append(values)
    return displayresults


def get_search_results(query):
    results = {}
    scores = []
    query, _, lang = parse_query(query.lower())
    if lang is None:
        languages = LANGS
    else:
        languages = [lang]
    for lang in languages:
        if glob(join(pod_dir,'*',lang)) == []:
            continue
        clean_query = ' '.join([w for w in query.split() if w not in models[lang]['stopwords']])
        print("\n\n>>>>>>>>>>>>>>>>>>>>>>")
        print(">> SEARCH:CONTROLLERS:get_search_results: searching in",lang)
        print(">>>>>>>>>>>>>>>>>>>>>>")
        try:
            r, s = score_pages.run_search(clean_query, lang)
            #r, s = score_pages.run_search_decentralized(clean_query, lang)
            results.update(r)
            scores.extend(s)
        except:
            pass
    sorted_scores = np.argsort(scores)[::-1]
    sorted_results = {}
    for i in sorted_scores:
        url = list(results.keys())[i]
        sorted_results[url] = results[url]
    logging.debug(f"SORTED RESULTS: {sorted_results}")
    return sorted_results

