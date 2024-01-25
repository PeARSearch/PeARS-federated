# SPDX-FileCopyrightText: 2022 PeARS Project, <community@pearsproject.org>, 
#
# SPDX-License-Identifier: AGPL-3.0-only

# Import flask dependencies
from flask import Blueprint, request, render_template, send_from_directory
from flask import current_app

# Import the database object from the main app module
from app.api.models import Urls
from app.search import score_pages

# Import matrix manipulation modules
import numpy as np
from scipy import sparse

# Import utilities
import re
import logging
from os.path import dirname, join, realpath, isfile
from app.utils import init_podsum, beautify_title, beautify_snippet
from app import EXPERT_ADD_ON, OWN_BRAND, WALKTHROUGH, STOPWORDS

LOG = logging.getLogger(__name__)

# Define the blueprint:
search = Blueprint('search', __name__, url_prefix='')

dir_path = dirname(dirname(dirname(realpath(__file__))))
static_dir = join(dir_path,'app','static')
pod_dir = join(dir_path,'app','static','pods')


@search.context_processor
def inject_brand():
    return dict(own_brand=OWN_BRAND)

@search.route('/')
@search.route('/index')
def index():  
    results = []
    internal_message = ""
    if Urls.query.count() == 0:
        init_podsum()

    query = request.args.get('q')
    if not query:
        if OWN_BRAND:
            with open(join(static_dir,'intro.txt'), 'r') as file:
                internal_message = file.read().replace('\n', '<br>')
        return render_template("search/index.html", internal_message=internal_message, own_brand=OWN_BRAND)
    else:
        pears = ['0.0.0.0']
        displayresults = []
        query = ' '.join([w for w in query.split() if w not in STOPWORDS])
        if WALKTHROUGH:
            with open(join(static_dir,'walkthrough.txt'), 'r') as file:
                internal_message = file.read().replace('\n', '<br>')
        results, pods = score_pages.run(query, pears)
        if not results:
            pears = ['no results found :(']
            results = [{'url':None, 'title':None, 'snippet':'No pages found', 'doctype':None, 'notes':None, 'img':None, 'trigger':None, 'contributor':None}]
        for r in results:
            if r['doctype'] != 'csv':
                r['snippet'] = ' '.join(r['snippet'].split()[:11]) #11 to conform with EU regulations
            r['title'] = beautify_title(r['title'], r['doctype'])
            r['snippet'] = beautify_snippet(r['snippet'], r['img'], query, EXPERT_ADD_ON)
            displayresults.append(list(r.values()))
        query = query.replace(' ','&nbsp;')
        return render_template('search/results.html', pears=[], query=query, results=displayresults, internal_message=internal_message, expert=EXPERT_ADD_ON, own_brand=OWN_BRAND)

@search.route('/experts/<kwd>/<idx>/')
def experts(kwd,idx):  
    print(idx,kwd)
    displayresults = []
    results, pods = score_pages.score_experts(idx,kwd)
    if not results:
        pears = ['no pear found :(']
        results = [{'url':None, 'title':None, 'snippet':'No pages found', 'doctype':None, 'notes':None, 'img':None, 'trigger':None, 'contributor':None}]
    for r in results:
        r['title'] = beautify_title(r['title'], r['doctype'])
        r['snippet'] = beautify_snippet(r['snippet'], r['img'], 'ind', EXPERT_ADD_ON)
        displayresults.append(list(r.values()))
    return render_template('search/results.html', pears=[], query="-", results=displayresults, expert=EXPERT_ADD_ON, own_brand=OWN_BRAND)

@search.route('/html_cache/<path:filename>')
def custom_static(filename):
    return send_from_directory('html_cache', filename)
