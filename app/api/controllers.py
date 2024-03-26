# SPDX-FileCopyrightText: 2023 PeARS Project, <community@pearsproject.org>, 
#
# SPDX-License-Identifier: AGPL-3.0-only

import joblib
from os import remove
from os.path import dirname, join, realpath, isfile
from flask import Blueprint, jsonify, request, render_template, url_for
from flask_login import login_required
from scipy.sparse import vstack, save_npz, load_npz
from app.api.models import Urls, Pods
from app.auth.decorators import check_is_confirmed
from app import db, models, OWN_BRAND
from app.indexer.posix import load_posix, dump_posix
from app.search.controllers import prepare_gui_results
from app.utils_db import load_idx_to_url, load_npz_to_idx, rm_from_idx_to_url, delete_pod_representations

# Define the blueprint:
api = Blueprint('api', __name__, url_prefix='/api')

dir_path = dirname(dirname(realpath(__file__)))
pod_dir = join(dir_path,'static','pods')


@login_required
@check_is_confirmed
@api.route('/pods/')
def return_pods():
    return jsonify(json_list=[p.serialize for p in Pods.query.all()])

@login_required
@check_is_confirmed
@api.route('/pods/<pod>/')
def return_pod(pod):
    pod = pod.replace('+', ' ')
    p = db.session.query(Pods).filter_by(name=pod).first()
    return jsonify(p.serialize)

@login_required
@check_is_confirmed
@api.route('/pods/delete', methods=["GET","POST"])
def return_pod_delete(pod_name):
    print("Unsubscribing pod...", pod_name)
    delete_pod_representations(pod_name)

@login_required
@check_is_confirmed
@api.route('/urls/')
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
            internal_message=internal_message, own_brand=OWN_BRAND)


@login_required
@check_is_confirmed
@api.route('/urls/delete', methods=["GET","POST"])
def return_url_delete(path):
    u = db.session.query(Urls).filter_by(url=path).first()
    pod_name = u.pod
    theme, contributor = pod_name.split('.u.')
    pod = db.session.query(Pods).filter_by(name=pod_name).first()
    lang = pod.language
    vocab = models[lang]['vocab']

    #Remove document from main .idx file
    idx = delete_url_from_url_to_idx(path, contributor)

    #Find out index of url
    npz_to_idx, npz_to_idx_path = load_npz_to_idx(contributor, lang, theme)
    print("NPZ_TO_IDX")
    print(npz_to_idx)
    j = npz_to_idx[1].index(idx)
    vid = npz_to_idx[0].index(j)
    print(theme, contributor)
    print(path, vid, pod_name)

    #Remove document row from .npz matrix
    pod_m = load_npz(join(pod_dir, contributor, lang, pod_name+'.npz'))
    print("pod_m",pod_m.shape)
    print("vid",vid)
    m1 = pod_m[:vid]
    m2 = pod_m[vid+1:]
    print("m1",m1.shape)
    print("m2",m2.shape)
    pod_m = vstack((m1,m2))
    print("pod_m",pod_m.shape)
    save_npz(join(pod_dir, contributor, lang, pod_name+'.npz'),pod_m)

    #Remove document from .npz.idx mapping
    new_npz = npz_to_idx[0][:j]+npz_to_idx[0][j+1:]
    new_idx = npz_to_idx[1][:j]+npz_to_idx[1][j+1:]
    npz_to_idx = [new_npz,new_idx]
    joblib.dump(npz_to_idx, npz_to_idx_path)
    print("NPZ_TO_IDX")
    print(npz_to_idx)

    #Remove doc from positional index
    posindex = load_posix(contributor, lang, theme)
    new_posindex = []
    for token in vocab:
        token_id = vocab[token]
        tmp = {}
        for doc_id, posidx in posindex[token_id].items():
            if doc_id != str(vid):
                tmp[doc_id] = posidx
        new_posindex.append(tmp)
    dump_posix(new_posindex, contributor, lang, theme)

    #Delete from database
    db.session.delete(u)
    db.session.commit()

    #If pod is now empty, delete it
    print(pod_m.shape)
    if pod_m.shape[0] == 1:
        return_pod_delete(pod_name)
    return "Deleted document with vector id"+str(vid)


