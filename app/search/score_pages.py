# SPDX-FileCopyrightText: 2024 PeARS Project, <community@pearsproject.org>, 
#
# SPDX-License-Identifier: AGPL-3.0-only

from os import getenv
from os.path import dirname, join, realpath
import logging
import math
from time import time
from itertools import islice
from urllib.parse import urlparse
from flask import url_for
from glob import glob
import joblib
from joblib import Parallel, delayed
from scipy.sparse import load_npz
from scipy.spatial import distance
import numpy as np
from app import db
from app.api.models import Urls
from app.search.overlap_calculation import (snippet_overlap,
        score_url_overlap, posix, posix_no_seq)
from app.utils import parse_query, timer
from app.utils_db import load_idx_to_url, load_npz_to_idx
from app.indexer.mk_page_vector import compute_query_vectors
from app.indexer.posix import load_posix

dir_path = dirname(dirname(realpath(__file__)))
pod_dir = getenv("PODS_DIR", join(dir_path, 'pods'))

def intersect_best_pods_lists(query_vectors, podsum, podnames):
    """ Iterate through each word in the query (a vector of tokens)
    and compute the best 5 pods for that word. Then intersect all
    lists and return the best pods, together with their scores."""
    tmp_best_pods = []
    m_cosines = []
    for query_vector in query_vectors:
        cos = 1 - distance.cdist(query_vector, podsum, 'cosine')
        idx = np.argsort(cos, axis=1)[:,-5:][0][::-1]
        tmp_best_pods.append(idx)
        m_cosines.append(cos[0])
    m_cosines = np.array(m_cosines)
    q_best_pods = set.intersection(*map(set,tmp_best_pods))
    if len(q_best_pods) == 0:
        q_best_pods = set.union(*map(set,tmp_best_pods))
    best_pods = {}
    for p in q_best_pods:
        podname = podnames[p]
        podscore = np.sum(m_cosines.T[p])
        best_pods[podname] = podscore
    best_pods = dict(sorted(best_pods.items(), key=lambda item: item[1], reverse=True))
    best_pods = dict(islice(best_pods.items(), 3))
    return best_pods


def intersect_best_cos_lists(query_vectors, pod_m):
    """ Iterate through each word in the query (a vector of tokens)
    and compute the best 100 docs for that word using cosine distance. 
    Then intersect all lists and return the best docs, together with 
    their scores."""
    tmp_best_docs = []
    m_cosines = []
    for query_vector in query_vectors:
        cos = 1 - distance.cdist(query_vector, pod_m, 'cosine')
        idx = np.argsort(cos, axis=1)[:,-100:][0][::-1]
        tmp_best_docs.append(idx)
        m_cosines.append(cos[0])
    m_cosines = np.array(m_cosines)
    q_best_docs = set.intersection(*map(set,tmp_best_docs))
    if len(q_best_docs) == 0:
        q_best_docs = set.union(*map(set,tmp_best_docs))
    best_docs = {}
    for d in q_best_docs:
        docscore = np.mean(m_cosines.T[d])
        best_docs[d] = docscore
    logging.info(f"BEST DOCS FROM COSINES: {best_docs}")
    return best_docs

def intersect_best_posix_lists(query_tokenized, posindex, lang):
    tmp_best_docs = []
    posix_scores = {}
    # Loop throught the token list corresponding to each word
    for word_tokens in query_tokenized:
        scores = posix(' '.join(word_tokens), posindex, lang)
        logging.debug(f"POSIX SCORES: {scores}")
        tmp_best_docs.append(list(scores.keys()))
        for k,v in scores.items():
            if k in posix_scores:
                posix_scores[k].append(v)
            else:
                posix_scores[k] = [v]
    q_best_docs = set.intersection(*map(set,tmp_best_docs))
    if len(q_best_docs) == 0:
        q_best_docs = set.union(*map(set,tmp_best_docs))
    best_docs = {}
    for d in q_best_docs:
        #Here we sum because we want as many words as possible
        #to be covered by the document
        docscore = np.sum(posix_scores[d])
        best_docs[d] = docscore
    logging.info(f"BEST DOCS FROM POS INDEX: {best_docs}")
    return best_docs



@timer
def compute_scores(query, query_vectors, query_tokenized, pod_name, posindex, lang):
    """Compute different scores for a query
    Arguments:
    query: the original query
    query_vectors: a list of vectors, one vector per word in the
    query (because each word has several tokens)
    query_tokenized: a list of lists of tokens, one list per word.
    pod_name: the pod we are scoring against
    posindex: the positional index for that pod
    """
    print("\n>> SEARCH:SCORE_PAGES:compute_scores on pod", pod_name)
    vec_scores = {}
    theme = pod_name.split('.u.')[0]
    username = pod_name.split('.u.')[1]
    user_dir = join(pod_dir, username)
    pod_m = load_npz(join(user_dir, lang, pod_name+'.npz'))

    # Compute score of each document for each word
    best_cos_docs = intersect_best_cos_lists(query_vectors, pod_m.todense())
    best_posix_docs = intersect_best_posix_lists(query_tokenized, posindex, lang)

    idx_to_url, _ = load_idx_to_url(username)
    npz_to_idx, _ = load_npz_to_idx(username, lang, theme) 
    logging.debug(f"idx_to_url {idx_to_url}")
    logging.debug(f"npz_to_idx {npz_to_idx}")

    for i in range(pod_m.shape[0]):
        cos = best_cos_docs.get(i,0)
        if  cos == 0 or math.isnan(cos):
            continue
        #Get doc idx for row i of the matrix
        idx = npz_to_idx[1][i]
        #print("IDX",idx)
        #Get list position of doc idx in idx_to_url
        lspos = idx_to_url[0].index(idx)
        #print("LSPOS",lspos)
        #Retrieve corresponding URL
        url = idx_to_url[1][lspos]
        #print("URL",url)
        vec_scores[url] = cos
    return vec_scores, best_posix_docs


def mk_podsum_matrix(lang):
    """ Make the podsum matrix, i.e. a matrix
    with each row corresponding to the sum of 
    all documents in a given pod."""
    podnames = []
    podsum = []
    npzs = glob(join(pod_dir,'*',lang,'*.u.*npz'))
    for npz in npzs:
        podname = npz.split('/')[-1].replace('.npz','')
        s = np.sum(load_npz(npz).toarray(), axis=0)
        #print(podname, np.sum(s), s)
        if np.sum(s) > 0:
            podsum.append(s)
            podnames.append(podname)
    return podnames, podsum

@timer
def score_pods(query_vectors, extended_q_vectors, lang):
    """Score pods for a query.

    We score pods with respect to the original query as well as the extended
    query. To do this, we first compute cosine between the query / elements
    of the extended query and each podsum vector, resulting in a matrix of 
    cosines for each computation. Then, we hit the database to attach a pod
    name to each score.

    Parameters:
    query_vector: the numpy array for the query (dim = size of vocab)
    extended_q_vectors: a list of numpy arrays for the extended query
    lang: the language of the query

    Returns: a list of the best <max_pods: int> pods, or if all scores
    are under a certain threshold, the list of all pods.
    """
    print(">> SEARCH: SCORE PAGES: SCORE PODS")

    max_pods = 3 # How many pods to return
    quality_threshold = 0.05 # Minimum score for a pod to be considered okay
    pod_scores = {}
    podnames, podsum = mk_podsum_matrix(lang)

    # For each word in the query, compute best pods
    pod_scores = intersect_best_pods_lists(query_vectors, podsum, podnames)

    if max(pod_scores.values()) < quality_threshold:
        # Compute similarity of each extended query element to all pods
        pod_scores = intersect_best_pods_lists(extended_q_vectors, podsum, podnames)

    best_pods = []
    for k in sorted(pod_scores, key=pod_scores.get, reverse=True):
        if len(best_pods) < max_pods:
            logging.info(f"\t>> Appending best pod {k}, score {pod_scores[k]}")
            best_pods.append(k)
        else:
            break
    return best_pods

@timer
def score_docs(query, query_vectors, query_tokenized, pod_name, posindex, lang):
    """Score documents for a query.
    Arguments:
    query: the original query
    query_vectors: a list of lists of vectors, one list per word in the
    query (because each word has several tokens)
    query_tokenized: a list of lists of tokens, one list per word.
    pod_name: the pod we are scoring against
    posindex: the positional index for that pod
    """
    print("\n>> INFO: SEARCH: SCORE_PAGES: SCORE_DOCS", pod_name)
    print(">> SEARCH:SCORE_PAGES:score_docs starting at", time())
    document_scores = {}  # Document scores
    vec_scores, posix_scores = \
            compute_scores(query, query_vectors, query_tokenized, pod_name, posindex, lang)
    username = pod_name.split('.u.')[1]
    user_dir = join(pod_dir, username)
    idx_to_url = joblib.load(join(user_dir, username+'.idx'))
    for url in list(vec_scores.keys()):
        i = idx_to_url[1].index(url)
        idx = idx_to_url[0][i]
        document_scores[url] = vec_scores[url]
        document_scores[url] += posix_scores.get(idx, 0)
        #print(">>>",url, "VEC", vec_scores[url], "POSIX",document_scores[url])
        if math.isnan(document_scores[url]) or document_scores[url] < 1:
            document_scores[url] = 0
        else:
            u = db.session.query(Urls).filter_by(url=url).first()
            #print(url, u.title+' '+u.snippet)
            snippet_score = snippet_overlap(query, u.title+' '+u.snippet)
            if snippet_score > 0:
                snippet_score = snippet_score*10 #push up the urls with matches in title or snippet
            document_scores[url]+=snippet_score
            logging.debug(f"url: {url}, vec_score: {vec_scores[url]}, posix_score: {posix_scores.get(idx,0)}, snippet_score: {snippet_score} ||| GRAND SCORE: {document_scores[url]}")
    return document_scores

@timer
def score_docs_extended(extended_q_tokenized, pod_name, posindex, lang):
    '''Score documents for an extended query, using posix scoring only'''
    print(">> INFO: SEARCH: SCORE_PAGES: SCORE_DOCS_EXTENDED",pod_name)
    print(">> SEARCH:SCORE_PAGES:score_docs_extended starting at", time())
    document_scores = {}  # Document scores
    theme = pod_name.split('.u.')[0]
    username = pod_name.split('.u.')[1]
    user_dir = join(pod_dir, username)
    idx_to_url = joblib.load(join(user_dir, username+'.idx'))
    npz_to_idx = load_npz_to_idx(username, lang, theme) 
    for w_tokenized in extended_q_tokenized:
        logging.debug(f"WORD-TOKENIZED: {w_tokenized}")
        # Keep a list of urls already increment by 1, we don't want
        # to score several times within the same neighbourhood
        urls_incremented = []
        matching_docs = posix_no_seq(' '.join(w_tokenized), posindex, lang)
        logging.debug(f"MATCHING DOCS: {matching_docs}")
        for v in matching_docs:
            logging.debug(f"MATCHING DOC: {v}, {urls_incremented}")
            logging.debug(f"idx_to_url {idx_to_url}")
            i = idx_to_url[0].index(v)
            url = idx_to_url[1][i]
            u = db.session.query(Urls).filter_by(pod=pod_name).filter_by(url=url).first()
            if u:
                if url not in urls_incremented:
                    if url in document_scores:
                        document_scores[url] += 1
                    else:
                        document_scores[url] = 1
                    urls_incremented.append(url)
            else:
                print(">> ERROR: SCORE PAGES: score_docs_extended: url not found")
    logging.info(f"DOCUMENT SCORES: {document_scores}")
    return document_scores

def return_best_urls(doc_scores):
    best_urls = []
    scores = []
    netlocs_used = []  # Don't return 100 pages from the same site
    c = 0
    for w in sorted(doc_scores, key=doc_scores.get, reverse=True):
        loc = urlparse(w).netloc
        if c < 50:
            if doc_scores[w] >= 0.5:
                #if netlocs_used.count(loc) < 10:
                #print("DOC SCORE",w,doc_scores[w])
                best_urls.append(w)
                scores.append(doc_scores[w])
                netlocs_used.append(loc)
                c += 1
            else:
                break
        else:
            break
    return best_urls, scores


def output(best_urls):
    results = {}
    for u in best_urls:
        url = db.session.query(Urls).filter_by(url=u).first().as_dict()
        if u.startswith('pearslocal'):
            u = url_for('api.return_specific_url')+'?url='+u
        url['url'] = u
        results[u] = url
    return results


def run_search(query:str, lang:str):
    """Run search on query input by user

    Search happens in three steps. 1) We get the pods most likely
    to contain documents relevant to the query. 2) We run search 
    on the original query. 3) We run search on an 'extended' query
    consisting of distributional neighbours of the original words.

    Parameter: query, a query string.
    Returns: a list of documents. Each document is a dictionary. 
    """
    document_scores = {}

    # Set up multithreading to use half of CPU count
    #max_thread = int(multiprocessing.cpu_count() * 0.75)
    max_thread = 1

    # Run tokenization and vectorization on query. We also get an extended query and its vector.
    q_tokenized, extended_q_tokenized, q_vectors, extended_q_vectors = compute_query_vectors(query, lang)

    # Get best pods
    best_pods = score_pods(q_vectors, extended_q_vectors, lang)
   
    # Load positional indices
    posindices = []
    for pod in best_pods:
        theme = pod.split('.u.')[0]
        contributor = pod.split('.u.')[1]
        posindices.append(load_posix(contributor, lang, theme))

    # Compute results for original query
    logging.info(f"BEST PODS: {best_pods}")
    with Parallel(n_jobs=max_thread, prefer="threads") as parallel:
        delayed_funcs = [delayed(score_docs)(query, q_vectors, q_tokenized, best_pods[i], posindices[i], lang) for i in range(len(best_pods))]
        scores = parallel(delayed_funcs)
    for dic in scores:
        document_scores.update(dic)
    logging.debug(f"DOCUMENT SCORES 1: {document_scores}")

    # Compute results for extended query
    extended_document_scores = {}
    with Parallel(n_jobs=max_thread, prefer="threads") as parallel:
        delayed_funcs = [delayed(score_docs_extended)(extended_q_tokenized, best_pods[i], posindices[i], lang) for i in range(len(best_pods))]
        scores = parallel(delayed_funcs)
    for dic in scores:
        extended_document_scores.update(dic)
    logging.debug(f"DOCUMENT SCORES 2: {extended_document_scores}")
    #print(set(extended_document_scores.keys())-set(document_scores.keys()))

    # Merge
    merged_scores = document_scores.copy()
    for k,v in extended_document_scores.items():
        if k in document_scores:
            merged_scores[k] = document_scores[k]+ 0.5*extended_document_scores[k]
        else:
            merged_scores[k] = 0.5*extended_document_scores[k]

    logging.debug(f"DOCUMENT SCORES MERGED: {merged_scores}")
    best_urls, scores = return_best_urls(merged_scores)
    results = output(best_urls)
    return results, scores
