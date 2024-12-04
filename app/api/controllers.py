# SPDX-FileCopyrightText: 2023 PeARS Project, <community@pearsproject.org>, 
#
# SPDX-License-Identifier: AGPL-3.0-only

import joblib
import json
import numpy as np
from os import remove, getenv
from os.path import dirname, join, realpath, isfile
from flask import Blueprint, jsonify, request, render_template, url_for
from scipy.sparse import vstack, save_npz, load_npz
from app.forms import SearchForm
from app.api.models import Urls, Pods
from app.auth.decorators import check_permissions, check_is_confirmed
from app import app, db, models
from app.indexer.posix import load_posix, dump_posix
from app.indexer.vectorizer import scale
from app.search.controllers import get_search_results, prepare_gui_results
from app.search.score_pages import mk_podsum_matrix
from app.utils_db import delete_pod_representations, create_suggestion_in_db

# Define the blueprint:
api = Blueprint('api', __name__, url_prefix='/api')

dir_path = dirname(dirname(realpath(__file__)))
pod_dir = getenv("PODS_DIR", join(dir_path, 'pods'))

@api.route('/languages/', methods=["GET", "POST"])
def return_instance_languages():
    """Returns the languages of this instance.
    For use by other PeARS instances."""
    return jsonify(json_list=app.config['LANGS'])

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
    results = get_search_results(query)
    return jsonify(json_list=results)

@api.route('/urls/')
@check_permissions(login=True, confirmed=True)
def return_urls():
    return jsonify(json_list=[i.serialize for i in Urls.query.all()])

@api.route('/get', methods=["GET"])
def return_specific_url():
    internal_message = ""
    u = request.args.get('url')
    url = db.session.query(Urls).filter_by(url=u).first().as_dict()
    if u.startswith('pearslocal'):
        u = url_for('api.return_specific_url')+'?url='+u
        url['url'] = u
    displayresults = prepare_gui_results("",{u:url})
    return render_template('search/results.html', query="", results=displayresults, \
            internal_message=internal_message, searchform=SearchForm())
