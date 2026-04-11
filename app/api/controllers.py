# SPDX-FileCopyrightText: 2023 PeARS Project, <community@pearsproject.org>, 
#
# SPDX-License-Identifier: AGPL-3.0-only

import json
from os import getenv
from os.path import dirname, join, realpath
import numpy as np
from flask import current_app
from flask import Blueprint, jsonify, request, render_template, url_for
from scipy.sparse import save_npz
from app.forms import SearchForm
from app.api.models import Urls
from app.auth.decorators import check_permissions
from app.extensions import db
from app.indexer.vectorizer import scale
from app.search.controllers import get_local_search_results, prepare_gui_results
from app.search.score_pages import mk_podsum_matrix
from app.utils import beautify_pears_content

# Define the blueprint:
api = Blueprint('api', __name__, url_prefix='/api')

dir_path = dirname(dirname(realpath(__file__)))
pod_dir = getenv("PODS_DIR", join(dir_path, 'pods'))

@api.route('/languages/', methods=["GET", "POST"])
def return_instance_languages():
    """Returns the languages of this instance.
    For use by other PeARS instances."""
    return jsonify(json_list=current_app.config['LANGS'])

@api.route('/identity', methods=["GET", "POST"])
def return_identity_info():
    return jsonify({
        "sitename": current_app.config["SITENAME"],
        "site_topic": current_app.config["SITE_TOPIC"],
        "organization": current_app.config["ORG_NAME"] 
    })

@api.route('/signature/<lang>/', methods=["GET", "POST"])
def return_instance_signature(lang):
    """Returns the signature of this instance for a language.
    For use by other PeARS instances."""
    _, podsum = mk_podsum_matrix(lang)
    podsum = np.array(podsum)
    podsum = scale(podsum) #L2 normalization
    signature = np.sum(podsum, axis=0)
    return json.dumps(signature.tolist())

@api.route('/search', methods=["GET"])
def return_query_results():
    """Returns the results for a query in a json format.
    For use by other PeARS instances."""
    query = request.args.get('q')
    _, results = get_local_search_results(query)
    return jsonify(json_list=results)

@api.route('/urls/')
@check_permissions(login=True, confirmed=True)
def return_urls():
    return jsonify(json_list=[i.serialize for i in Urls.query.all()])


@api.route('/get', methods=["GET"])
def return_specific_url():
    internal_message = ""
    u = request.full_path.split('api/get?url=')[1]
    url = db.session.query(Urls).filter_by(url=u).first().as_dict()
    url["instance"] = current_app.config["SITENAME"]
    if u.startswith('content') or u.startswith('comment'):
        u = url_for('api.display_content')+'?url='+u
        url['url'] = u
    displayresults = prepare_gui_results("",{u:url})
    return render_template('search/results.html', query="", results=displayresults, \
            internal_message=internal_message, searchform=SearchForm())


@api.route('/show', methods=["GET"])
def display_content():
    u = request.full_path.split('api/show?url=')[1]
    url = db.session.query(Urls).filter_by(url=u).first()
    content = beautify_pears_content(url.content)
    comment = True if u.startswith('comment') else False
    return render_template('search/display.html', title=url.title, contributor=url.contributor, \
            date=url.date_created, share_url=url.share, content=content, comment=comment)
