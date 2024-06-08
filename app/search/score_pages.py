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

def intersect_best_pods_lists(query_words, query_vectors, podsum, podnames, max_pods):
    """ Iterate through each word in the query (a vector of tokens)
    and compute the best 5 pods for that word. Then intersect all
    lists and return the best pods, together with their scores."""
    tmp_best_pods = []
    m_cosines = []
    q_best_pods = []
    podsum = np.array(podsum)
    for i, query_vector in enumerate(query_vectors):
        cos = 1 - distance.cdist(query_vector, podsum, 'cosine')
        cos[np.isnan(cos)] = 0
        m_cosines.append(cos[0])
    m_cosines = np.array(m_cosines)
    maximums = np.amax(m_cosines, axis=1)
    best_pods = {}
    #for p in q_best_pods:
    for p in range(len(podnames)):
        if np.sum(m_cosines.T[p]) == 0:
            continue
        podname = podnames[p]
        podscore = 1 - distance.cdist([maximums],[m_cosines.T[p]], 'euclidean')[0][0]
        logging.debug(f"POD {podnames[p]} {m_cosines.T[p]} {podscore}")
        best_pods[podname] = podscore
    best_pods = dict(sorted(best_pods.items(), key=lambda item: item[1], reverse=True))
    best_pods = dict(islice(best_pods.items(), max_pods))
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
        cos[np.isnan(cos)] = 0
        idx = np.argsort(cos, axis=1)[:,-100:][0][::-1]
        tmp_best_docs.append(idx)
        m_cosines.append(cos[0])
    m_cosines = np.array(m_cosines)
    q_best_docs = set.intersection(*map(set,tmp_best_docs))
    if len(q_best_docs) == 0:
        q_best_docs = set.union(*map(set,tmp_best_docs))
    maximums = np.amax(m_cosines, axis=1)
    best_docs = {}
    for d in q_best_docs:
        if np.sum(m_cosines.T[d]) == 0:
            continue
        #docscore = np.nanmean(m_cosines.T[d])
        docscore = 1 - distance.cdist(np.array([maximums]),[m_cosines.T[d]], 'euclidean')[0][0]
        #print(d, maximums, m_cosines.T[d], docscore)
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
        docscore = np.mean(posix_scores[d])
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
    #logging.debug(f"idx_to_url {idx_to_url}")
    #logging.debug(f"npz_to_idx {npz_to_idx}")

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


def mk_vec_matrix(lang):
    """ Make a vector matrix by stacking all
    pod matrices."""
    c = 0
    podnames = []
    bins = [c]
    npzs = glob(join(pod_dir,'*',lang,'*.u.*npz'))
    for npz in npzs:
        podnames.append(npz.split('/')[-1].replace('.npz',''))
    m = load_npz(npzs[0]).toarray()
    c+=m.shape[0]
    bins.append(c)
    for i in range(1,len(npzs)):
        npz = load_npz(npzs[i]).toarray()
        m = vstack((m, npz))
        c+=npz.shape[0]
        bins.append(c)
    m = csr_matrix(m)
    return m, bins, podnames



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

    if 'm' in models[lang]:
        m = models[lang]['m'].todense()
        bins = models[lang]['mbins']
        podnames = models[lang]['podnames']
    else:
        m, bins, podnames = mk_vec_matrix(lang)

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


@timer
def score_pods_legacy(query_words, query_vectors, extended_q_vectors, lang):
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

    max_pods = app.config["MAX_PODS"] # How many pods to return
    quality_threshold = 0.05 # Minimum score for a pod to be considered okay
    pod_scores = {}

    if 'podsum' in models[lang]:
        podnames = models[lang]['podnames']
        podsum = models[lang]['podsum']
    else:
        podnames, podsum = mk_podsum_matrix(lang)

    # For each word in the query, compute best pods
    pod_scores = intersect_best_pods_lists(query_words, query_vectors, podsum, podnames, max_pods)

    if max(pod_scores.values()) < quality_threshold:
        # Compute similarity of each extended query element to all pods
        pod_scores = intersect_best_pods_lists(query_words, extended_q_vectors, podsum, podnames, max_pods)

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
    snippet_length = app.config['SNIPPET_LENGTH']
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
        #print(">>>",url, "POSIX",posix_scores.get(idx,0))
        #print(">>>",url, "VEC", vec_scores[url], "POSIX",posix_scores.get(idx,0))
        if math.isnan(document_scores[url]) or document_scores[url] < 1:
            document_scores[url] = 0
        else:
            u = db.session.query(Urls).filter_by(url=url).first()
            snippet = ' '.join(u.snippet.split()[:snippet_length])
            snippet_score = snippet_overlap(query, u.title+' '+snippet)
            #print(">>>",url, u.title+' '+snippet[:50], snippet_score)
            if snippet_score > 0:
                snippet_score = snippet_score*10 #push up the urls with matches in title or snippet
            document_scores[url]+=snippet_score
            logging.debug(f"url: {u.title}, vec_score: {vec_scores[url]}, posix_score: {posix_scores.get(idx,0)}, snippet_score: {snippet_score} ||| GRAND SCORE: {document_scores[url]}")
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
            #logging.debug(f"MATCHING DOC: {v}, {urls_incremented}")
            #logging.debug(f"idx_to_url {idx_to_url}")
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
    best_pods = score_pods(q_tokenized, q_vectors, extended_q_vectors, lang)
   
    # Load positional indices
    posindices = []
    for pod in best_pods:
        theme = pod.split('.u.')[0]
        contributor = pod.split('.u.')[1]
        if 'posix' in models[lang] and theme in models[lang]['posix']:
            print("Using posix in RAM for ", pod)
            posindices.append(models[lang]['posix'][theme])
        else:
            print("Loading posix for ", pod)
            posindices.append(load_posix(contributor, lang, theme))

    # Compute results for original query
    logging.info(f"BEST PODS: {best_pods}")
    with Parallel(n_jobs=max_thread) as parallel:
        delayed_funcs = [delayed(score_docs)(query, q_vectors, q_tokenized, best_pods[i], posindices[i], lang) for i in range(len(best_pods))]
        scores = parallel(delayed_funcs)
    for dic in scores:
        document_scores.update(dic)
    logging.debug(f"DOCUMENT SCORES 1: {document_scores}")

    # Compute results for extended query
    #extended_document_scores = {}
    #with Parallel(n_jobs=max_thread) as parallel:
    #    delayed_funcs = [delayed(score_docs_extended)(extended_q_tokenized, best_pods[i], posindices[i], lang) for i in range(len(best_pods))]
    #    scores = parallel(delayed_funcs)
    #for dic in scores:
    #    extended_document_scores.update(dic)
    #logging.debug(f"DOCUMENT SCORES 2: {extended_document_scores}")
    #print(set(extended_document_scores.keys())-set(document_scores.keys()))

    # Merge
    merged_scores = document_scores.copy()
    #for k,v in extended_document_scores.items():
    #    if k in document_scores:
    #        merged_scores[k] = document_scores[k]+ 0.5*extended_document_scores[k]
    #    else:
    #        merged_scores[k] = 0.5*extended_document_scores[k]

    logging.debug(f"DOCUMENT SCORES MERGED: {merged_scores}")
    best_urls, scores = return_best_urls(merged_scores)
    results = output(best_urls)
    return results, scores
