# SPDX-FileCopyrightText: 2022 PeARS Project, <community@pearsproject.org>, 
#
# SPDX-License-Identifier: AGPL-3.0-only

import multiprocessing
from joblib import Parallel, delayed
from urllib.parse import urlparse
import re
import math
from pandas import read_csv
from app.api.models import Urls, Pods
from app import db, LANG, VEC_SIZE
from app.utils_db import get_db_url_snippet, get_db_url_title, get_db_url_doctype, get_db_url_pod, get_db_url_notes

from .overlap_calculation import score_url_overlap, generic_overlap, completeness, posix, posix_no_seq
from app.search import term_cosine
from app.utils import cosine_similarity, hamming_similarity, convert_to_array, parse_query, timer
from app.indexer.mk_page_vector import tokenize_text, compute_query_vectors
from app.indexer.posix import load_posix
from scipy.sparse import csr_matrix, load_npz
from scipy.spatial import distance
from os.path import dirname, join, realpath, isfile
import numpy as np

dir_path = dirname(dirname(realpath(__file__)))
pod_dir = join(dir_path,'static','pods')
raw_dir = join(dir_path,'static','userdata')


def score_experts(doc_idx,kwd):
    DS_scores = {}
    query_pod_m = load_npz(join(pod_dir,kwd+'.npz'))
    query_vec = query_pod_m[int(doc_idx)].todense().reshape(1,VEC_SIZE)
    ind_pod_m = load_npz(join(pod_dir,'Individuals.npz'))
    m_cosines = 1 - distance.cdist(query_vec, ind_pod_m.todense(), 'cosine')
    
    for u in db.session.query(Urls).filter_by(pod='Individuals').all():
        score = m_cosines[0][int(u.vector)]
        if score >= 0.05:
            DS_scores[u.url] = m_cosines[0][int(u.vector)]
            print("EXPERT",u.url,score)
    urls = bestURLs(DS_scores)
    return output(urls, 'ind')

@timer
def score(query, query_vector, tokenized, kwd, posindex):
    URL_scores = {}
    snippet_scores = {}
    DS_scores = {}
    completeness_scores = {}
    posix_scores = posix(tokenized, kwd, posindex)

    pod_m = load_npz(join(pod_dir,kwd+'.npz'))
    m_cosines = 1 - distance.cdist(query_vector, pod_m.todense(), 'cosine')
    m_completeness = completeness(query_vector, pod_m.todense())

    for u in db.session.query(Urls).filter_by(pod=kwd).all():
        DS_scores[u.url] = m_cosines[0][int(u.vector)]
        completeness_scores[u.url] = m_completeness[0][int(u.vector)]
        #URL_scores[u.url] = score_url_overlap(query, u.url)
        #snippet_scores[u.url] = generic_overlap(query, u.title+' '+u.snippet)
        snippet_scores[u.url] = generic_overlap(query, u.title)
        #print("SNIPPET SCORE",u.url,snippet_scores[u.url])
    return DS_scores, completeness_scores, snippet_scores, posix_scores

@timer
def score_pods(query_vector, extended_q_vectors, lang):
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
    quality_threshold = 0.01 # Minimum score for a pod to be considered okay
    pod_scores = {}

    # Compute similarity of query to all pods
    podsum = load_npz(join(pod_dir,'podsum.npz'))
    m_cosines = 1 - distance.cdist(query_vector, podsum.todense(), 'cosine')

    # Compute similarity of each extended query element to all pods
    extended_m_cosines = []
    for nns_vector in extended_q_vectors:
        extended_m_cosines.append(1 - distance.cdist(nns_vector, podsum.todense(), 'cosine'))

    # For each pod, retrieve cosine to query as well as overlap to extended query
    pods = db.session.query(Pods).filter_by(language=lang).filter_by(registered=True).all()
    for p in pods:
        cosine_score = m_cosines[0][int(p.DS_vector)]
        if math.isnan(cosine_score):
            cosine_score = 0
        extended_score = 0
        for m in extended_m_cosines:
            extended_score += m[0][int(p.DS_vector)]
        pod_scores[p.name] = cosine_score + extended_score

    #If all scores are rubbish, search entire pod collection (we're desperate!)
    if max(pod_scores.values()) < quality_threshold:
        return list(pod_scores.keys())
    else:
        best_pods = []
        for k in sorted(pod_scores, key=pod_scores.get, reverse=True):
            if len(best_pods) < max_pods: 
                print("\t>> Appending best pod",k, pod_scores[k])
                best_pods.append(k)
            else:
                break
        return best_pods


def score_docs(query, query_vector, tokenized, pod, posindex):
    '''Score documents for a query'''
    print(">> INFO: SEARCH: SCORE_PAGES: SCORES_DOCS",pod)
    document_scores = {}  # Document scores
    DS_scores, completeness_scores, snippet_scores, posix_scores = score(query, query_vector, tokenized, pod, posindex)
    #if len(posix_scores) != 0:
    #    print("POSIX SCORES",posix_scores)
    for url in list(DS_scores.keys()):
        document_score = 0.0
        idx = db.session.query(Urls).filter_by(url=url).first().vector #We assume a url can only belong to one pod
        if idx in posix_scores:
            document_score = posix_scores[idx]
        document_score = document_score + completeness_scores[url] + snippet_scores[url]
        if snippet_scores[url] > 0:
            document_score+=snippet_scores[url]*10 #bonus points
        if math.isnan(document_score): # or completeness_scores[url] < 0.3:  # Check for potential NaN -- messes up with sorting in bestURLs.
            document_score = 0
        if document_score > 0:
            #print(url, document_score, completeness_scores[url], snippet_scores[url])
            document_scores[url] = document_score
    return document_scores

def score_docs_extended(extended_q_tokenized, pod, posindex):
    '''Score documents for an extended query, using posix scoring only'''
    print(">> INFO: SEARCH: SCORE_PAGES: SCORES_DOCS_EXTENDED",pod)
    document_scores = {}  # Document scores
    for w_tokenized in extended_q_tokenized:
        #print("W TOKENIZED",w_tokenized)
        urls_incremented = [] # Keep list of urls already increment by 1, we don't want to score several times within the same neighbourhood
        matching_docs = posix_no_seq(' '.join(w_tokenized), pod, posindex)
        #print("MATCHING DOCS", matching_docs)
        for v in matching_docs:
            url = db.session.query(Urls).filter_by(pod=pod).filter_by(vector=v).first() #We assume a url can only belong to one pod
            if url:
                url = url.url
                if url not in urls_incremented:
                    if url in document_scores:
                        document_scores[url] += 1
                    else:
                        document_scores[url] = 1
                    urls_incremented.append(url)
                    #print(v,document_scores[url])
            else:
                print(">> ERROR: SCORE PAGES: score_docs_extended: url not found")
    return document_scores

def bestURLs(doc_scores):
    best_urls = []
    netlocs_used = []  # Don't return 100 pages from the same site
    c = 0
    for w in sorted(doc_scores, key=doc_scores.get, reverse=True):
        loc = urlparse(w).netloc
        if c < 50:
            if doc_scores[w] > 1:
                #if netlocs_used.count(loc) < 10:
                #print("DOC SCORE",w,doc_scores[w])
                best_urls.append(w)
                netlocs_used.append(loc)
                c += 1
            else:
                break
        else:
            break
    #print("BEST URLS",best_urls)
    return best_urls


def aggregate_csv(best_urls):
    urls = list([u for u in best_urls if '.csv#' not in u])
    print("AGGREGATE URLS:",urls)
    csvs = []
    csv_names = list([re.sub('#.*','',u) for u in best_urls if '.csv#' in u])
    csv_names_set_preserved_order = []
    for c in csv_names:
        if c not in csv_names_set_preserved_order:
            csv_names_set_preserved_order.append(c)
    print("AGGREGATE CSV NAMES:",csv_names_set_preserved_order)
    for csv_name in csv_names_set_preserved_order:
        rows = [re.sub('.*\[','',u)[:-1] for u in best_urls if csv_name in u]
        first_url = ''
        for u in best_urls:
            if csv_name in u:
                first_url = u
                break
        csvs.append([csv_name, first_url, rows])
        print(rows)
    return urls, csvs


def assemble_csv_table(csv_name,rows,doctype):
    try:
        df = read_csv(join(raw_dir,'csv',csv_name), delimiter=';', encoding='utf-8')
    except:
        df = read_csv(join(raw_dir,'csv',csv_name), delimiter=';', encoding='iso-8859-1')
    df_slice = df.iloc[rows].to_numpy()
    table = "<table class='table table-striped w-100'><thead><tr>"
    if doctype == 'map':
        table+="<th scope='col' style='word-wrap:break-word; max-width:500px'>www</th>"
    for c in list(df.columns):
        table+="<th scope='col' style='word-wrap:break-word; max-width:500px'>"+c+"</th>"
    table+="</tr></thead>"
    for r in df_slice[:10]:
        #table+="""<tr class='w-100' onclick='document.location="https://en.wikipedia.org"' style='cursor: pointer'>"""
        table+="<tr class='w-100'>"
        if doctype == 'map':
            link="https://www.openstreetmap.org/#map=19/"+str(r[0])+"/"+str(r[1])
            #table+="<td><a href='https://www.openstreetmap.org/#map=19/"+str(r[0])+"/"+str(r[1])+"'>📍</a></td>"
            table+="""<td><a href="#" onClick="console.log('"""+link+"""'); window.open('"""+link+"""', 'pagename', 'resizable,height=560,width=560,top=200,left=800');return false;">📍</a><noscript>You need Javascript to use the previous link or use <a href='"""+link+"""' target="_blank">📍</a></noscript></td>"""
        for i in r:
            table+="<td style='word-wrap:break-word; max-width:500px'>"+str(i)+"</td>"
        table+="</tr>"
    table+="</table>"
    return table



def output_with_csv(best_urls, doctype):
    print("DOCTYPE",doctype)
    results = []
    pods = []
    if len(best_urls) == 0:
        return results, pods
    urls, csvs = aggregate_csv(best_urls)

    for csv in csvs:
        rec = Urls.query.filter(Urls.url == csv[1]).first()
        if doctype != None and rec.doctype != doctype:
            continue
        result = {}
        result['id'] = rec.id
        result['url'] = csv[0]
        result['title'] = csv[0]
        result['snippet'] = assemble_csv_table(csv[0],csv[2],rec.doctype)
        result['doctype'] = rec.doctype
        result['notes'] = None
        result['idx'] = rec.vector
        result['pod'] = rec.pod
        result['img'] = None
        result['trigger'] = rec.trigger
        result['contributor'] = rec.contributor
        results.append(result)

    for u in urls:
        rec = Urls.query.filter(Urls.url == u).first()
        if doctype != None and rec.doctype != doctype:
            continue
        result = {}
        result['id'] = rec.id
        result['url'] = rec.url
        result['title'] = rec.title
        result['snippet'] = rec.snippet
        result['doctype'] = rec.doctype
        result['notes'] = rec.notes
        result['idx'] = rec.vector
        result['pod'] = rec.pod
        result['img'] = rec.img
        result['trigger'] = rec.trigger
        result['contributor'] = rec.contributor
        results.append(result)
        pod = rec.pod
        if pod not in pods:
            pods.append(pod)
    return results, pods


def output(best_urls):
    results = []
    pods = []
    for u in best_urls:
        rec = Urls.query.filter(Urls.url == u).first()
        result = {}
        result['id'] = rec.id
        result['url'] = rec.url
        result['title'] = rec.title
        result['snippet'] = rec.snippet
        result['doctype'] = rec.doctype
        result['notes'] = rec.notes
        result['idx'] = rec.vector
        result['pod'] = rec.pod
        result['img'] = rec.img
        result['trigger'] = rec.trigger
        result['contributor'] = rec.contributor
        results.append(result)
        pod = rec.pod
        if pod not in pods:
            pods.append(pod)
    return results, pods


def run_search(q:str):
    """Run search on query input by user

    Search happens in three steps. 1) We get the pods most likely
    to contain documents relevant to the query. 2) We run search 
    on the original query. 3) We run search on an 'extended' query
    consisting of distributional neighbours of the original words.

    Parameter: q, a query string.
    Returns: a list of documents. Each document is a dictionary. 
    """

    # Set up multithreading to use half of CPU count
    max_thread = int(multiprocessing.cpu_count() * 0.75)

    # Get doctype and language from query in case they are there
    query, doctype, lang = parse_query(q)

    # Run tokenization and vectorization on query. We also get an extended query and its vector.
    q_tokenized, extended_q_tokenized, q_vectors, extended_q_vectors = compute_query_vectors(query, lang)

    # Get best pods
    best_pods = score_pods(q_vectors, extended_q_vectors, lang)
    print("Q:",query,"BEST PODS:",best_pods)
   
    # Load positional indices
    posindices = []
    for pod in best_pods:
        posindices.append(load_posix(pod))

    # Compute results for original query
    document_scores = {}
    with Parallel(n_jobs=max_thread, prefer="threads") as parallel:
        delayed_funcs = [delayed(score_docs)(query, q_vectors, q_tokenized, best_pods[i], posindices[i]) for i in range(len(best_pods))]
        scores = parallel(delayed_funcs)
    for dic in scores:
        document_scores.update(dic)

    # Compute results for extended query
    extended_document_scores = {}
    with Parallel(n_jobs=max_thread, prefer="threads") as parallel:
        delayed_funcs = [delayed(score_docs_extended)(extended_q_tokenized, best_pods[i], posindices[i]) for i in range(len(best_pods))]
        scores = parallel(delayed_funcs)
    for dic in scores:
        extended_document_scores.update(dic)

    # Merge
    #print("DOCUMENT SCORES 1",document_scores)
    #print("DOCUMENT SCORES 2",extended_document_scores)
    merged_scores = document_scores.copy()
    for k,v in extended_document_scores.items():
        if k in document_scores:
            merged_scores[k] = document_scores[k]+ 0.5*extended_document_scores[k]
        else:
            merged_scores[k] = 0.5*extended_document_scores[k]

    #print("DOCUMENT SCORES MERGED",merged_scores)
    best_urls = bestURLs(merged_scores)
    results, pods = output(best_urls)
    return results
