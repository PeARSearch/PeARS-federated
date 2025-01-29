# SPDX-FileCopyrightText: 2024 PeARS Project, <community@pearsproject.org> 
#
# SPDX-License-Identifier: AGPL-3.0-only

import logging
import datetime
from os import remove, rename, getenv
from os.path import dirname, realpath, join, isfile
from pathlib import Path
from string import punctuation
import joblib
from sqlalchemy import update
import numpy as np
from scipy.sparse import csr_matrix, load_npz, vstack, save_npz
from app import db, models, VEC_SIZE
from app.api.models import AccessLogs, Urls, Pods, Suggestions
from app.indexer.posix import load_posix, dump_posix

dir_path = dirname(dirname(realpath(__file__)))
pod_dir = getenv("PODS_DIR", join(dir_path, 'app', 'pods'))

def parse_pod_name(pod_name):
    logging.debug(f">> UTILS_DB: parse_pod_name: {pod_name}")
    theme = pod_name.split('.u.')[0]
    contributor = pod_name.split('.u.')[1]
    lang = Pods.query.filter_by(name=pod_name).first().language
    return contributor, theme, lang


###########
# Access logging
###########

def create_access_log_entry(
    user_logged_in, 
    user_id, 
    user_is_confirmed, 
    user_is_admin,
    user_email,
    event_type,
    endpoint,
    request_url,
    response_code,
    messages
):
    log = AccessLogs(
        user_logged_in,
        user_id,
        user_is_confirmed,
        user_is_admin,
        user_email,
        event_type,
        endpoint,
        request_url,
        response_code,
        messages
    )
    db.session.add(log)
    db.session.commit()


def compute_daily_access_stats():
    today = datetime.date.today()
    yesterday = today - datetime.timedelta(days=1)
    before_yesterday = today - datetime.timedelta(days=2) 
    
    successful_access_logs_today = (
        db.session.query(AccessLogs)
        .filter(AccessLogs.log_date > yesterday)
        .filter(AccessLogs.response_code.between(199,400))
        .all()
    )
    successful_access_logs_yesterday = (
        db.session.query(AccessLogs)
        .filter(AccessLogs.log_date
        .between(before_yesterday, yesterday))
        .filter(AccessLogs.response_code.between(199,400))
        .all()
    )

    failed_access_logs_today = (
        db.session.query(AccessLogs)
        .filter(AccessLogs.log_date > yesterday)
        .filter(AccessLogs.response_code.between(399, 600))
        .all()
    )

    failed_access_logs_yesterday = (
        db.session.query(AccessLogs)
        .filter(AccessLogs.log_date.between(before_yesterday, yesterday))
        .filter(AccessLogs.response_code.between(399, 600))
        .all()
    )

    total_requests_today = len(successful_access_logs_today) + len(failed_access_logs_today) 
    total_requests_yesterday = len(successful_access_logs_yesterday) + len(failed_access_logs_yesterday) 

    successful_logins_today = (
        db.session.query(AccessLogs)
        .filter(AccessLogs.log_date > yesterday)
        .filter(AccessLogs.endpoint == "auth.login")
        .filter(AccessLogs.event_type == "auth_success")
        .all()
    )

    successful_logins_yesterday = (
        db.session.query(AccessLogs)
        .filter(AccessLogs.log_date.between(before_yesterday, yesterday))
        .filter(AccessLogs.endpoint == "auth.login")
        .filter(AccessLogs.event_type == "auth_success")
        .all()
    )

    failed_logins_today = (
        db.session.query(AccessLogs)
        .filter(AccessLogs.log_date > yesterday)
        .filter(AccessLogs.endpoint == "auth.login")
        .filter(AccessLogs.event_type == "auth_failure")
        .all()
    )

    failed_logins_yesterday = (
        db.session.query(AccessLogs)
        .filter(AccessLogs.log_date.between(before_yesterday, yesterday))
        .filter(AccessLogs.endpoint == "auth.login")
        .filter(AccessLogs.event_type == "auth_failure")
        .all()
    )

    total_logins_today = len(successful_logins_today) + len(failed_logins_today)
    total_logins_yesterday = len(successful_logins_yesterday) + len(failed_logins_yesterday)

    unique_users_today = (
        db.session.query(AccessLogs)
        .filter(AccessLogs.log_date > yesterday)
        .filter(AccessLogs.user_id != -1)
        .group_by(AccessLogs.user_id)
        .count()
    )

    unique_users_yesterday = (
        db.session.query(AccessLogs)
        .filter(AccessLogs.log_date.between(before_yesterday, yesterday))
        .filter(AccessLogs.user_id != -1)
        .group_by(AccessLogs.user_id)
        .count()
    )

    return {
        "date": f"{today.year}-{today.month}-{today.day}",
        "total_requests": total_requests_today,
        "total_requests_diff": total_requests_yesterday - total_requests_today,
        "successful_requests": len(successful_access_logs_today),
        "successful_requests_diff": len(successful_access_logs_today) - len(successful_access_logs_yesterday),
        "failed_requests": len(failed_access_logs_today),
        "failed_requests_diff": len(failed_access_logs_today) - len(failed_access_logs_yesterday),
        
        "total_logins": total_logins_today,
        "total_logins_diff": total_logins_today - total_logins_yesterday,
        "successful_logins": len(successful_logins_today),
        "successful_logins_diff": len(successful_logins_today) - len(successful_logins_yesterday),
        "failed_logins": len(failed_logins_today),
        "failed_logins_diff": len(failed_logins_today) - len(failed_logins_yesterday),

        "unique_users": unique_users_today,
        "unique_users_diff": unique_users_today - unique_users_yesterday
    }


###########
# Creating
###########

def create_pod_npz_pos(contributor, theme, lang):
    """ Pod npz and pos initialisation.
    This happens when the user indexes for the 
    first time under a specific theme.
    """
    user_dir = join(pod_dir,contributor, lang)
    Path(user_dir).mkdir(parents=True, exist_ok=True)
    pod_path = join(user_dir, theme+'.u.'+contributor )
    vocab = models[lang]['vocab']
    if not isfile(pod_path+'.npz'):
        logging.debug(">> UTILS_DB: create_pod_npz_pos: Making 0 CSR matrix for new pod")
        pod = np.zeros((1,VEC_SIZE))
        pod = csr_matrix(pod)
        save_npz(pod_path+'.npz', pod)
        logging.debug(f">> UTILS_DB: create_pod_npz_pos: {pod.shape[0]}")

    if not isfile(pod_path+'.pos'):
        logging.debug(">> UTILS_DB: create_pod_npz_pos: Making empty positional index for new pod")
        posindex = [{} for _ in range(len(vocab))]
        joblib.dump(posindex, pod_path+'.pos')
    return pod_path


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

def create_suggestion_in_db(url, pod, notes, contributor):
    '''Add suggestion to database'''
    s = Suggestions(url=url, pod=pod, notes=notes, contributor=contributor)
    db.session.add(s)
    db.session.commit()

def create_or_replace_url_in_db(url, title, idv, snippet, theme, lang, note, share, contributor, entry_type):
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
    u.vector = idv
    u.snippet = snippet
    u.pod = theme+'.u.'+contributor
    u.language = lang
    u.share = share
    u.contributor = contributor
    u.doctype = entry_type
    u.cc = cc
    if note != '':
        note = '@'+contributor+' >> '+note
        if u.notes is not None:
            u.notes = u.notes+'<br>'+note
        else:
            u.notes = note
    db.session.add(u)
    db.session.commit()
    return u.id


##########
# Adding
##########

def add_to_npz(v, pod_path):
    """ Add new pre-computed vector to npz matrix.
    Arguments:
    v: the vector to add
    pod_path: the path to the target pod

    Returns:
    vid: the new row number for the vector
    """
    pod_m = load_npz(pod_path)
    pod_m = vstack((pod_m,csr_matrix(v)))
    save_npz(pod_path, pod_m)
    vid = pod_m.shape[0]
    return vid


############
# Deleting
############

def delete_pod_representations(pod_name):
    if '.u.' in pod_name:
        theme, contributor = pod_name.split('.u.')
        logging.debug(theme, contributor)
    else:
        theme = pod_name
        contributor = None
    pod = db.session.query(Pods).filter_by(name=pod_name).first()
    lang = pod.language
    urls = db.session.query(Urls).filter_by(pod=pod_name).all()
    if urls is not None:
        for u in urls:
            #This is going to be slow for many urls...
            db.session.delete(u)
            db.session.commit()
    npz_path = join(pod_dir, contributor, lang, pod_name+'.npz')
    if isfile(npz_path):
        remove(npz_path)
    npz_idx_path = join(pod_dir, contributor, lang, pod_name+'.npz.idx')
    if isfile(npz_idx_path):
        remove(npz_idx_path)
    pos_path = join(pod_dir, contributor, lang, pod_name+'.pos')
    if isfile(pos_path):
        remove(pos_path)
    db.session.delete(pod)
    db.session.commit()


def delete_url_representations(url):
    """ Delete url with some url on some pod.
    """
    u = db.session.query(Urls).filter_by(url=url).first()
    pod = u.pod
    username = pod.split('.u.')[1]
    logging.debug(f">> UTILS_DB: delete_url_representations: POD {pod}, USER {username}")

    #Remove document row from .npz matrix
    try:
        idv, _ = rm_from_npz(u.vector, pod)
        update_db_idvs_after_npz_delete(idv, pod)
    except:
        logging.debug(f">> UTILS_DB: delete_url_representations: could not remove vector from npz file.")

    #Remove doc from positional index
    try:
        rm_doc_from_pos(u.id, pod)
    except:
        logging.debug(f">> UTILS_DB: delete_url_representations: could not remove vector from pos file.")

    #Delete from database
    db.session.delete(u)
    db.session.commit()

    #If pod empty, delete
    if len(db.session.query(Urls).filter_by(pod=pod).all()) == 0:
        delete_pod_representations(pod)
    
    return "Deleted document with url "+url


def rm_from_npz(vid, pod_name):
    """ Remove vector from npz file.
    Arguments:
    vid: the row number of the vector
    pod_path: the path to the pod containing the vector

    Returns: the deleted vector
    """
    contributor, _, lang = parse_pod_name(pod_name)
    pod_path = join(pod_dir, contributor, lang, pod_name+'.npz')
    pod_m = load_npz(pod_path)
    logging.debug(f">> UTILS_DB: rm_from_npz: SHAPE OF NPZ MATRIX BEFORE RM: {pod_m.shape}")
    v = pod_m[vid]
    logging.debug(f">> UTILS_DB: rm_from_npz: CHECKING SHAPE OF DELETED VEC: {pod_m.shape}")
    m1 = pod_m[:vid]
    m2 = pod_m[vid+1:]
    pod_m = vstack((m1,m2))
    logging.debug(f">> UTILS_DB: rm_from_npz: SHAPE OF NPZ MATRIX AFTER RM: {pod_m.shape}")
    save_npz(pod_path, pod_m)
    return vid, v

##############
# CLEANING
##############
def update_db_idvs_after_npz_delete(idv, pod):
    condition = (Urls.pod == pod) & (Urls.vector > idv)
    update_stmt = update(Urls).where(condition).values(vector=Urls.vector-1)
    db.session.execute(update_stmt)


def rm_doc_from_pos(vid, pod):
    """ Remove wordpieces from pos file.
    Arguments:
    vid: the ID of the vector recording the wordpieces
    pod: the name of the pod

    Returns: the content of the positional index for that vector.
    """
    contributor, theme, lang = parse_pod_name(pod)
    vocab = models[lang]['vocab']
    posindex = load_posix(contributor, lang, theme)
    remaining_posindex = []
    deleted_posindex = []
    logging.debug(f">> UTILS_DB: rm_from_npz: DELETING DOC ID {vid}")
    for token in vocab:
        token_id = vocab[token]
        tmp_remaining = {}
        tmp_deleted = {}
        for doc_id, posidx in posindex[token_id].items():
            if doc_id != vid:
                tmp_remaining[doc_id] = posidx
            else:
                tmp_deleted[doc_id] = posidx
        remaining_posindex.append(tmp_remaining)
        deleted_posindex.append(tmp_deleted)
    dump_posix(remaining_posindex, contributor, lang, theme)
    return deleted_posindex

##########
# Renaming
##########


def mv_pod(src, target, contributor=None):
    if any(x in punctuation for x in target):
        return "Disallowed characters in new pod name. Please do not use punctuation."
    pods = db.session.query(Pods).all()
    contributor_pods = []
    for pod in pods:
        if pod.name[-len(contributor)-3:] == '.u.'+contributor:
            contributor_pods.append(pod.name.split('.u.')[0])
    #logging.debug(src,contributor_pods)
    if src not in contributor_pods:
        return "You cannot rename pods that you have never made a contribution to."
    if target in contributor_pods:
        return "You cannot use a pod name that you have already created in the past." #TODO: change this.
    lang = Pods.query.filter_by(name=src+'.u.'+contributor).first().language
    pod_path = join(pod_dir, contributor, lang)
    try:
        src = src+'.u.'+contributor
        target = target+'.u.'+contributor
        p = db.session.query(Pods).filter_by(name=src).first()

        #Rename npz
        src_path = join(pod_path,src+'.npz')
        target_path = join(pod_path,target+'.npz')
        rename(src_path, target_path)

        #Rename npz to idx
        src_path = join(pod_path,src+'.npz.idx')
        target_path = join(pod_path,target+'.npz.idx')
        rename(src_path, target_path)

        #Rename pos
        src_path = join(pod_path,src+'.pos')
        target_path = join(pod_path,target+'.pos')
        rename(src_path, target_path)
        
        #Rename in DB
        logging.debug(p.name)
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
    return "Moved pod "+src.split('.u.')[0]+" to "+target.split('.u.')[0]
