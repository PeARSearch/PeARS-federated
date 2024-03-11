# SPDX-FileCopyrightText: 2024 PeARS Project, <community@pearsproject.org> 
#
# SPDX-License-Identifier: AGPL-3.0-only

from os.path import dirname, realpath, join, isfile
from pathlib import Path
import joblib
import numpy as np
from scipy.sparse import csr_matrix, save_npz
from app import db, vocab, VEC_SIZE
from app.api.models import Urls, Pods

dir_path = dirname(dirname(realpath(__file__)))
pod_dir = join(dir_path,'app','static','pods')


def create_idx_to_url(contributor):
    """ Doc ID to URL table initialisation.
    This happens once when the user indexes
    for the first time.
    """
    # One idx to url dictionary per user
    user_dir = join(pod_dir,contributor)
    Path(user_dir).mkdir(parents=True, exist_ok=True)
    user_path = join(user_dir, contributor+'.idx')
    if not isfile(user_path):
        print("Making idx dictionaries for new user.")
        idx_to_url = [[],[]]
        joblib.dump(idx_to_url, user_path)


def create_pod_npz_pos(contributor, theme, lang):
    """ Pod npz and pos initialisation.
    This happens when the user indexes for the 
    first time under a specific theme.
    """
    user_dir = join(pod_dir,contributor, lang)
    Path(user_dir).mkdir(parents=True, exist_ok=True)
    pod_path = join(user_dir, theme+'.u.'+contributor )
    if not isfile(pod_path+'.npz'):
        print("Making 0 CSR matrix for new pod")
        pod = np.zeros((1,VEC_SIZE))
        pod = csr_matrix(pod)
        save_npz(pod_path+'.npz', pod)

    if not isfile(pod_path+'.pos'):
        print("Making empty positional index for new pod")
        posindex = [{} for _ in range(len(vocab))]
        joblib.dump(posindex, pod_path+'.pos')

    if not isfile(pod_path+'.npz.idx'):
        print("Making idx dictionaries for new pod")
        # Lists of lists to make deletions easier
        npz_to_idx = [[0],[-1]] # For row 0 of the matrix
        joblib.dump(npz_to_idx, pod_path+'.npz.idx')


def create_pod_in_db(contributor, theme, lang):
    '''If the pod does not exist, create it in the database.
    '''
    if contributor is not None:
        theme = theme+'.u.'+contributor
    url = join("http://localhost:8080/api/pods/",contributor,lang,theme.replace(' ', '+'))
    if not db.session.query(Pods).filter_by(url=url).all():
        p = Pods(url=url)
        p.name = theme
        p.description = theme
        p.language = lang
        p.registered = True
        db.session.add(p)
        db.session.commit()

def add_to_idx_to_url(contributor, url):
    """Add an entry to the IDX to URL map.
    Arguments: username, url.
    Return: the newly create IDX for this url.
    """
    user_dir = join(pod_dir,contributor)
    pod_path = join(user_dir, contributor+'.idx')
    idx_to_url = joblib.load(pod_path)
    idx = len(idx_to_url[0])
    idx_to_url[0].append(idx)
    idx_to_url[1].append(url)
    joblib.dump(idx_to_url, pod_path)
    return idx

def add_to_npz_to_idx(pod_name, lang, vid, idx):
    """Record the ID of the document given
    its position in the npz matrix.
    NB: the lists do not have to be in the
    order of the matrix.
    """
    contributor = pod_name.split('.u.')[1]
    user_dir = join(pod_dir,contributor)
    pod_path = join(user_dir, lang, pod_name+'.npz.idx')
    npz_to_idx = joblib.load(pod_path)
    npz_to_idx[0].append(vid)
    npz_to_idx[1].append(idx)
    joblib.dump(npz_to_idx, pod_path)

def create_or_replace_url_in_db(url, title, snippet, theme, lang, note, contributor, entry_type):
    """Add a new URL to the database or update it.
    Arguments: url, title, snippet, theme, language,
    note warning, username, type (url or doc).
    """
    cc = False
    entry = db.session.query(Urls).filter_by(url=url).first()
    if entry:
        u = db.session.query(Urls).filter_by(url=url).first()
    else:
        u = Urls(url=url)
    u.title = title
    u.snippet = snippet
    u.pod = theme+'.u.'+contributor
    u.language = lang
    u.contributor = contributor
    u.doctype = entry_type
    u.cc = cc
    note = '@'+contributor+' >> '+note
    if u.notes is not None:
        u.notes = u.notes+'<br>'+note
    else:
        u.notes = note
    db.session.add(u)
    db.session.commit()
