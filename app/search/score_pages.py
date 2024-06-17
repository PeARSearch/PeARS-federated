# SPDX-FileCopyrightText: 2024 PeARS Project, <community@pearsproject.org>, 
#
# SPDX-License-Identifier: AGPL-3.0-only

import math
import logging
from time import time
from os import getenv
from os.path import dirname, join, realpath
from itertools import islice
from urllib.parse import urlparse
from glob import glob
from collections import Counter
import joblib
from joblib import Parallel, delayed
from scipy.spatial import distance
from scipy.sparse import load_npz, csr_matrix, vstack
import numpy as np
from flask import url_for
from app import app, db, models
from app.api.models import Urls
from app.search.overlap_calculation import (snippet_overlap,
        score_url_overlap, posix, posix_no_seq)
from app.utils import parse_query, timer
from app.utils_db import load_idx_to_url, load_npz_to_idx
from app.indexer.mk_page_vector import compute_query_vectors
from app.indexer.posix import load_posix

dir_path = dirname(dirname(realpath(__file__)))
pod_dir = getenv("PODS_DIR", join(dir_path, 'pods'))

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
def mk_vec_matrix(lang):
    """ Make a vector matrix by stacking all
    pod matrices."""
    c = 0
    podnames = []
    urls = []
    bins = [c]
    npzs = glob(join(pod_dir,'*',lang,'*.u.*npz'))
    for npz in npzs:
        podnames.append(npz.split('/')[-1].replace('.npz',''))
    m = load_npz(npzs[0]).toarray()
    c+=m.shape[0]
    bins.append(c)
    username = npzs[0].split('.u.')[1].replace('.npz','')
    idxs = joblib.load(join(pod_dir, username, lang, npzs[0].replace('.npz','')+'.npz.idx'))[1]
    idx_to_url = joblib.load(join(pod_dir, username, username+'.idx'))
    for idx in idxs:
        if idx in idx_to_url[0]:
            i = idx_to_url[0].index(idx)
            urls.append(idx_to_url[1][i])
        else:
            urls.append('none')
    for i in range(1,len(npzs)):
        npz = load_npz(npzs[i]).toarray()
        username = npzs[i].split('.u.')[1].replace('.npz','')
        m = vstack((m, npz))
        c+=npz.shape[0]
        bins.append(c)
        idxs = joblib.load(join(pod_dir, username, lang, npzs[i].replace('.npz','')+'.npz.idx'))[1]
        idx_to_url = joblib.load(join(pod_dir, username, username+'.idx'))
        for idx in idxs:
            if idx in idx_to_url[0]:
                i = idx_to_url[0].index(idx)
                urls.append(idx_to_url[1][i])
            else:
                urls.append('none')
    m = csr_matrix(m)
    return m, bins, podnames, urls


def load_vec_matrix(lang):
    if 'm' in models[lang]:
        m = models[lang]['m']
        bins = models[lang]['mbins']
        podnames = models[lang]['podnames']
        urls = models[lang]['urls']
    else:
        m, bins, podnames, urls = mk_vec_matrix(lang)
    m = m.todense()
    return m, bins, podnames, urls



@timer
def compute_scores(query, query_vectors, lang):
    snippet_length = app.config['SNIPPET_LENGTH']
    m, bins, podnames, urls = load_vec_matrix(lang)
    query_vector = np.sum(query_vectors, axis=0)
    
    # Only compute cosines over the dimensions of interest
    a = np.where(query_vector!=0)[1]
    cos = 1 - distance.cdist(query_vector[:,a], m[:,a], 'cosine')[0]
    cos[np.isnan(cos)] = 0

    # Document ids with non-zero values (match at least one subword)
    idx = np.where(cos!=0)[0]

    # Sort document ids with non-zero values
    idx = np.argsort(cos)[-len(idx):][::-1][:50]

    # Get urls
    document_scores = {}
    best_urls = [urls[i] for i in idx]
    best_cos = [cos[i] for i in idx]
    us = Urls.query.filter(Urls.url.in_(best_urls)).all()

    snippet_scores = {}
    for u in us:
        snippet = ' '.join(u.snippet.split()[:snippet_length])
        snippet_score = snippet_overlap(query, u.title+' '+snippet)
        snippet_scores[u.url] = snippet_score

    for i, u in enumerate(best_urls):
        #print(f"url: {u}, snippet_score: {snippet_scores[u]}, cos: {best_cos[i]}")
        document_scores[u] = best_cos[i] + snippet_scores[u]

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
    urls = Urls.query.filter(Urls.url.in_(best_urls)).all()
    urls = [next(u for u in urls if u.url == best_url) for best_url in best_urls]
    for u in urls:
        url = u.url
        if url.startswith('pearslocal'):
            url = url_for('api.return_specific_url')+'?url='+url
        results[url] = u.as_dict()
    return results


def run_search(query, lang, extended=True):
    """Run search on query input by user

    Parameter: query, a query string.
    Returns: a list of documents. Each document is a dictionary. 
    """
    document_scores = {}
    extended_document_scores = {}

    # Run tokenization and vectorization on query. We also get an extended query and its vector.
    q_tokenized, extended_q_tokenized, q_vectors, extended_q_vectors = compute_query_vectors(query, lang, expansion_length=10)

    document_scores = compute_scores(query, q_vectors, lang)

    if extended:
        extended_document_scores = compute_scores(query, extended_q_vectors, lang)

    # Merge
    merged_scores = document_scores.copy()
    for k,_ in extended_document_scores.items():
        if k in document_scores:
            merged_scores[k] = document_scores[k]+ 0.5*extended_document_scores[k]
        else:
            merged_scores[k] = 0.5*extended_document_scores[k]

    best_urls, scores = return_best_urls(merged_scores)
    results = output(best_urls)
    return results, scores




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
        docscore = np.mean(posix_scores[d])
        best_docs[d] = docscore
    logging.info(f"BEST DOCS FROM POS INDEX: {best_docs}")
    return best_docs


@timer
def score_pods(query_words, query_vectors, extended_q_vectors, lang):
    """Score pods for a query.

    Parameters:
    query_vector: the numpy array for the query (dim = size of vocab)
    extended_q_vectors: a list of numpy arrays for the extended query
    lang: the language of the query

    Returns: a list of the best <max_pods: int> pods.
    """
    print(">> SEARCH: SCORE PAGES: SCORE PODS")

    max_pods = app.config["MAX_PODS"] # How many pods to return
    pod_scores = {}

    m, bins, podnames = load_vec_matrix(lang)

    tmp_best_pods = []
    tmp_best_scores = []
    # For each word in the query, compute best pods
    for query_vector in query_vectors:
        # Only compute cosines over the dimensions of interest
        a = np.where(query_vector!=0)[1]
        cos = 1 - distance.cdist(query_vector[:,a], m[:,a], 'cosine')[0]
        cos[np.isnan(cos)] = 0

        # Document ids with non-zero values (match at least one subword)
        idx = np.where(cos!=0)[0]

        # Sort document ids with non-zero values
        idx = np.argsort(cos)[-len(idx):][::-1]

        # Bin document ids into pods, and record how many documents are matched in each bin
        d = np.digitize(idx, bins)
        d = dict(Counter(d).most_common())
        best_bins = list(d.keys())
        best_bins = [b-1 for b in best_bins] #digitize starts at 1, not 0
        print(best_bins)
        best_scores = list(d.values())
        max_score = max(best_scores)
        best_scores = np.array(best_scores) / max_score

        #pods = [podnames[b] for b in best_bins]
        tmp_best_pods.append(best_bins)
        tmp_best_scores.append(best_scores)

    best_pods = {}
    maximums = np.ones((1,len(query_vectors)))
    scores = np.zeros((1,len(query_vectors)))
    for p in range(len(podnames)):
        podname = podnames[p]
        for i, arr in enumerate(tmp_best_pods):
            score = tmp_best_scores[i][tmp_best_pods[i].index(p)] if p in tmp_best_pods[i] else 0
            scores[0][i] = score
        podscore = 1 - distance.cdist(maximums,scores, 'euclidean')[0][0]
        #if podscore != 0:
        #    print(f"POD {podnames[p]} {scores} {podscore}")
        best_pods[podname] = podscore
    best_pods = dict(sorted(best_pods.items(), key=lambda item: item[1], reverse=True))
    best_pods = dict(islice(best_pods.items(), max_pods))
    best_pods = list(best_pods.keys())
    return best_pods

