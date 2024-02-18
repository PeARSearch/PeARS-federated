# SPDX-FileCopyrightText: 2023 PeARS Project, <community@pearsproject.org>, 
#
# SPDX-License-Identifier: AGPL-3.0-only

# Import flask dependencies
from flask import Blueprint, jsonify, request

import numpy as np
from scipy.sparse import csr_matrix, vstack, save_npz, load_npz
from os.path import dirname, join, realpath, basename
from app.utils_db import create_or_update_pod
from app.api.models import Urls, Pods
from app import db, vocab, LANG, VEC_SIZE
from app.indexer.posix import load_posix, dump_posix
from os import remove, rename

# Define the blueprint:
api = Blueprint('api', __name__, url_prefix='/api')

dir_path = dirname(dirname(realpath(__file__)))
pod_dir = join(dir_path,'static','pods')


@api.route('/pods/')
def return_pods():
    return jsonify(json_list=[p.serialize for p in Pods.query.all()])

@api.route('/pods/<pod>/')
def return_pod(pod):
    pod = pod.replace('+', ' ')
    p = db.session.query(Pods).filter_by(name=pod).first()
    return jsonify(p.serialize)

@api.route('/pods/delete', methods=["GET","POST"])
def return_pod_delete(pod_name):
    print("Unsubscribing pod...", pod_name)
    if '.u.' in pod_name:
        theme, contributor = pod_name.split('.u.')
        print(theme, contributor)
    else:
        theme = pod_name
        contributor = None
    pod = db.session.query(Pods).filter_by(name=pod_name).first()
    lang = pod.language
    urls = db.session.query(Urls).filter_by(pod=pod_name).all()
    if urls is not None:
        for u in urls:
            db.session.delete(u)
            db.session.commit()
    print("Removing CSR matrix")
    remove(join(pod_dir,pod_name+'.npz'))
    print("Removing positional index")
    remove(join(pod_dir,pod_name+'.pos'))
    print("Reverting summary to 0")
    create_or_update_pod(contributor, theme, lang, np.zeros(VEC_SIZE))
    db.session.delete(pod)
    db.session.commit()


@api.route('/urls/')
def return_urls():
    return jsonify(json_list=[i.serialize for i in Urls.query.all()])


@api.route('/urls/delete', methods=["GET","POST"])
def return_url_delete(path):
    u = db.session.query(Urls).filter_by(url=path).first()
    pod_name = u.pod
    vid = int(u.vector)
    theme, contributor = pod_name.split('.u.')
    print(theme, contributor)
    print(path, vid, pod_name)

    #Remove document row from .npz matrix
    pod_m = load_npz(join(pod_dir,pod_name+'.npz'))
    m1 = pod_m[:vid]
    m2 = pod_m[vid+1:]
    pod_m = vstack((m1,m2)) 
    save_npz(join(pod_dir,pod_name+'.npz'),pod_m)

    #Correct indices in DB
    urls = db.session.query(Urls).filter_by(pod=pod_name).all()
    for url in urls:
        if int(url.vector) > vid:
            url.vector = str(int(url.vector)-1) #Decrease ID now that matrix row has gone
        db.session.add(url)
        db.session.commit()
   
    #Remove doc from positional index
    posindex = load_posix(pod_name)
    new_posindex = []
    for token in vocab:
        token_id = vocab[token]
        tmp = {}
        for doc_id, posidx in posindex[token_id].items():
            if doc_id != str(vid):
                tmp[doc_id] = posidx
        new_posindex.append(tmp)
    dump_posix(new_posindex,pod_name)

    #Recompute pod summary
    podsum = np.sum(pod_m, axis=0)
    create_or_update_pod(contributor, theme, LANG, podsum)
    db.session.delete(u)
    db.session.commit()
    return "Deleted document with vector id"+str(vid)


@api.route('/pods/move', methods=["GET","POST"])
def return_pod_rename(src, target, contributor=None):
    #if '.' in target:
    #    return "Disallowed characters in new pod name. Please do not use punctuation."
    #pods = db.session.query(Pods).all()
    #contributor_pods = []
    #for pod in pods:
    #    if pod.name[-len(contributor)+3:] == '.u.'+contributor:
    #        contributor_pods.append(pod.name.split('.u.')[0])
    #if src not in contributor_pods:
    #    return "You cannot rename pods that you have never made a contribution to."
    try:
        #src = src+'.u.'+contributor
        print("SRC",src)
        print("TARGET",target)
        p = db.session.query(Pods).filter_by(name=src).first()

        #Rename npz
        src_path = join(pod_dir,src+'.npz')
        print(src_path)
        target_path = join(pod_dir,target+'.npz')
        print(target_path)
        rename(src_path, target_path)

        #Rename pos
        src_path = join(pod_dir,src+'.pos')
        print(src_path)
        target_path = join(pod_dir,target+'.pos')
        print(target_path)
        rename(src_path, target_path)
        
        #Rename in DB
        print(p.name)
        p.name = target
        p.description = target
        p.url = join('http://localhost:8080/api/pods/',target.replace(' ','+'))
        db.session.add(p)
        db.session.commit()

        #Move all URLS
        urls = db.session.query(Urls).filter_by(pod=src).all()
        for url in urls:
            url.pod = target
            db.session.add(url)
            db.session.commit()
    except:
        return "Renaming failed. Contact your administrator."
    return "Moved pod "+src+" to "+target
