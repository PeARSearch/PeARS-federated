# SPDX-FileCopyrightText: 2024 PeARS Project, <community@pearsproject.org>, 
#
# SPDX-License-Identifier: AGPL-3.0-only

from os.path import dirname, join, realpath
from flask import Blueprint, request, render_template
from app.search import score_pages
from app.utils import beautify_title, beautify_snippet
from app import EXPERT_ADD_ON, OWN_BRAND, WALKTHROUGH, STOPWORDS

# Define the blueprint:
search = Blueprint('search', __name__, url_prefix='')

dir_path = dirname(dirname(dirname(realpath(__file__))))
static_dir = join(dir_path,'app','static')
pod_dir = join(dir_path,'app','static','pods')


@search.context_processor
def inject_brand():
    """Inject brand information into page
    (logo on all pages and info on start page.)
    """
    return dict(own_brand=OWN_BRAND)

@search.route('/')
@search.route('/index')
def index():
    """ Route for the main search page.
    """
    results = []
    internal_message = ""
    query = request.args.get('q')
    if not query:
        if OWN_BRAND:
            with open(join(static_dir,'intro.txt'), 'r', encoding="utf-8") as f:
                internal_message = f.read().replace('\n', '<br>')
        return render_template("search/index.html", internal_message=internal_message, \
                own_brand=OWN_BRAND)
    displayresults = []
    query = ' '.join([w for w in query.split() if w not in STOPWORDS])
    if WALKTHROUGH:
        with open(join(static_dir,'walkthrough.txt'), 'r', encoding="utf-8") as f:
            internal_message = f.read().replace('\n', '<br>')
    results = score_pages.run_search(query)
    if not results:
        results = None
        return render_template('search/results.html', \
                query=query, results=results, own_brand=OWN_BRAND)
    for r in results:
        if r['doctype'] != 'csv' and r['doctype'] != 'doc':
            r['snippet'] = ' '.join(r['snippet'].split()[:11]) #11 to conform with EU regulations
        r['title'] = beautify_title(r['title'], r['doctype'])
        r['snippet'] = beautify_snippet(r['snippet'], r['img'], query, EXPERT_ADD_ON)
        displayresults.append(list(r.values()))
    query = query.replace(' ','&nbsp;')
    return render_template('search/results.html', query=query, results=displayresults, \
            internal_message=internal_message, expert=EXPERT_ADD_ON, own_brand=OWN_BRAND)
