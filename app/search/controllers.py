# SPDX-FileCopyrightText: 2024 PeARS Project, <community@pearsproject.org>,
#
# SPDX-License-Identifier: AGPL-3.0-only

import logging
from os import getenv
from os.path import dirname, join, realpath
from glob import glob
import numpy as np
from random import shuffle
from urllib.parse import urlparse
from markupsafe import Markup
from flask import Blueprint, request, render_template, flash, url_for, redirect
from flask_login import current_user
from flask_babel import gettext
from app.forms import SearchForm
from app.search import score_pages
from app.utils import parse_query, beautify_title, beautify_snippet
from app import app, models, db
from app.api.models import Personalization
from app.search.cross_instance_search import get_cross_instance_results

# Define the blueprint:
search = Blueprint('search', __name__, url_prefix='')

dir_path = dirname(dirname(dirname(realpath(__file__))))
pod_dir = getenv("PODS_DIR", join(dir_path, 'app','pods'))


@search.route('/', methods=["GET","POST"])
def index():
    """ Route for the main search page.
    """
    results = []
    internal_message = ""
    searchform = SearchForm()

    if searchform.validate_on_submit():
        query = request.form.get('query').strip()
        messages = db.session.query(Personalization).filter_by(feature='tip').all()
        if messages:
            shuffle(messages)
            internal_message = messages[0].text


        clean_query, results = get_search_results(query)
        displayresults = prepare_gui_results(clean_query, results)
        return render_template('search/results.html', query=query, results=displayresults, \
                internal_message=internal_message, searchform=searchform)


    placeholder = app.config['SEARCH_PLACEHOLDER']
    searchform.query(render_kw={"placeholder": placeholder})
    if current_user.is_authenticated and not current_user.is_confirmed:
        message = Markup(gettext("You have not confirmed your account.<br>\
                Please use the link in the email that was sent to you, \
                or request a new link by clicking <a href='../auth/resend'>here</a>."))
        flash(message)
    if app.config['OWN_BRAND']:
        internal_message = db.session.query(Personalization).filter_by(feature='instance_info').first()
        if internal_message:
            internal_message = internal_message.text

    return render_template("search/index.html", internal_message=internal_message, \
            placeholder=placeholder, searchform=searchform)



def prepare_gui_results(query, results):
    if results is None or len(results) == 0:
        return None
    displayresults = []
    for url, r in results.items():
        r['title'] = ' '.join(r['title'].split()[:10])
        r['snippet'] = beautify_snippet(r['snippet'], query)
        logging.debug(f"RESULT URL {url}")
        if r['notes'] == 'None':
            r['notes'] = None
        else:
            r['notes'] = r['notes'].split('<br>')
        sitename = app.config['SITENAME']
        # results from our own instance
        share_url = r['share']
        if not share_url.startswith("https://"):
            share_url = "https://" + share_url
        print(f"share_url={share_url}, sitename={sitename}")
        if share_url.startswith(sitename):
            r['instance'] = urlparse(sitename).hostname
            r['instance_is_local'] = True
            r['instance_info_text'] = gettext("This result originates from the local PeARS instance.")
        # cross-instance results
        else:
            assert "x_instance_info" in r, f"Instance meta-info is missing in result:\n{r}"
            r['instance'] = r["x_instance_info"]["sitename"]
            r['instance_is_local'] = False
            instance_organization_text = r["x_instance_info"]["organization"] or "an unknown organization"
            instance_topic_text = r["x_instance_info"]["site_topic"]
            if instance_topic_text:
                _instance_info_text = gettext("This result originates from the remote PeARS instance \"{}\" ({}), which is maintained by {} and discusses the topic: {}")
                r["instance_info_text"] = _instance_info_text.format(r["instance"], r["x_instance_info"]["url"], instance_organization_text, instance_topic_text)
            else:
                _instance_info_text = gettext("This result originates from the remote PeARS instance \"{}\" ({}), which is maintained by {}.")
                r["instance_info_text"] = _instance_info_text.format(r["instance"], r["x_instance_info"]["url"], instance_organization_text)

        displayresults.append(r)
    return displayresults


def get_search_results(query):
    from app import instances
    clean_query = ""
    results = {}
    scores = []
    query, _, lang = parse_query(query.lower())
    if lang is None:
        languages = app.config['LANGS']
    else:
        languages = [lang]
    for lang in languages:
        clean_query = ' '.join([w for w in query.split() if w not in models[lang]['stopwords']])
        print("\n\n>>>>>>>>>>>>>>>>>>>>>>")
        print(">> SEARCH:CONTROLLERS:get_search_results: searching in",lang)
        print(">>>>>>>>>>>>>>>>>>>>>>")

        try:
            print("\n Getting results on this instance")
            r, s = score_pages.run_search(clean_query, lang, extended=app.config['EXTEND_QUERY'])
            results.update(r)
            scores.extend(s)
        except Exception as e:
            print(f"Error during local search: {e}")

        try:
            print("\n Getting results cross-instances")
            r = get_cross_instance_results(clean_query, instances)
            for url, dic in r.items():
                if url not in results:
                    results[url] = dic
                    scores.append(dic['score'])
        except:
            pass
    sorted_scores = np.argsort(scores)[::-1]
    sorted_results = {}
    for i in sorted_scores:
        url = list(results.keys())[i]
        sorted_results[url] = results[url]
    logging.debug(f"SORTED RESULTS: {sorted_results}")
    return clean_query, sorted_results


