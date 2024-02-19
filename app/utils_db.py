# SPDX-FileCopyrightText: 2023 PeARS Project, <community@pearsproject.org> 
#
# SPDX-License-Identifier: AGPL-3.0-only

import joblib
from app import db, VEC_SIZE
from app.api.models import Urls, Pods
from app.api.models import installed_languages
from app.utils import convert_to_array, convert_string_to_dict, convert_to_string, normalise
from app.indexer.mk_page_vector import compute_query_vectors
import numpy as np
from os.path import dirname, realpath, join
from scipy.sparse import csr_matrix, vstack, save_npz, load_npz

dir_path = dirname(dirname(realpath(__file__)))
pod_dir = join(dir_path,'app','static','pods')

def get_db_url_vector(url):
    url_vec = Urls.query.filter(Urls.url == url).first().vector
    return url_vec


def get_db_url_snippet(url):
    url_snippet = Urls.query.filter(Urls.url == url).first().snippet
    return url_snippet


def get_db_url_title(url):
    url_title = Urls.query.filter(Urls.url == url).first().title
    return url_title


def get_db_url_doctype(url):
    url_doctype = Urls.query.filter(Urls.url == url).first().doctype
    return url_doctype


def get_db_url_notes(url):
    url_notes = Urls.query.filter(Urls.url == url).first().notes
    return url_notes


def get_db_pod_name(url):
    pod_name = Pods.query.filter(Pods.url == url).first().name
    return pod_name


def get_db_url_pod(url):
    url_pod = Urls.query.filter(Urls.url == url).first().pod
    return url_pod


def get_db_pod_description(url):
    pod_description = Pods.query.filter(Pods.url == url).first().description
    return pod_description


def get_db_pod_language(url):
    pod_language = Pods.query.filter(Pods.url == url).first().language
    return pod_language


def compute_pod_summary(name):
    '''This function is very similar to 'self' in PeARS-pod'''
    DS_vector = np.zeros(VEC_SIZE) 
    #DS_vector = np.zeros(256) 
    for u in db.session.query(Urls).filter_by(pod=name).all():
        DS_vector += convert_to_array(u.vector)
    DS_vector = convert_to_string(normalise(DS_vector))
    c = 0
    return DS_vector


def url_from_json(url, pod):
    # print(url)
    if not db.session.query(Urls).filter_by(url=url['url']).all():
        u = Urls(url=url['url'])
        u.url = url['url']
        u.title = url['title']
        u.vector = url['vector']
        u.freqs = url['freqs']
        u.snippet = url['snippet']
        u.doctype = url['doctype']
        u.pod = pod
        db.session.add(u)
        db.session.commit()


def pod_from_json(pod, url):
    if not db.session.query(Pods).filter_by(url=url).all():
        p = Pods(url=url)
        db.session.add(p)
        db.session.commit()
    p = Pods.query.filter(Pods.url == url).first()
    p.name = pod['name']
    p.description = pod['description']
    p.language = pod['language']
    p.DS_vector = pod['DSvector']
    p.word_vector = pod['wordvector']
    if not p.registered:
        p.registered = False
    db.session.commit()


def create_or_update_pod(contributor, name, lang, podsum):
    '''If the pod does not exist, create it in the database.
    '''
    if contributor is not None:
        name = name+'.u.'+contributor
    url = "http://localhost:8080/api/pods/" + name.replace(' ', '+')
    if not db.session.query(Pods).filter_by(url=url).all():
        p = Pods(url=url)
        p.name = name
        p.description = name
        p.language = lang
        p.registered = True
        db.session.add(p)
        db.session.commit()
