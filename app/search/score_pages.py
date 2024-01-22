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
from app import db, VEC_SIZE
from app.utils_db import (
    get_db_url_snippet, get_db_url_title, get_db_url_doctype, get_db_url_pod, get_db_url_notes)

from .overlap_calculation import score_url_overlap, generic_overlap, completeness, posix
from app.search import term_cosine
from app.utils import cosine_similarity, hamming_similarity, convert_to_array, parse_query
from app.indexer.mk_page_vector import compute_query_vectors
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

def score(query, query_dist, tokenized, kwd):
    URL_scores = {}
    snippet_scores = {}
    DS_scores = {}
    completeness_scores = {}
    posix_scores = posix(tokenized, kwd)

    pod_m = load_npz(join(pod_dir,kwd+'.npz'))
    m_cosines = 1 - distance.cdist(query_dist, pod_m.todense(), 'cosine')
    m_completeness = completeness(query_dist, pod_m.todense())

    for u in db.session.query(Urls).filter_by(pod=kwd).all():
        DS_scores[u.url] = m_cosines[0][int(u.vector)]
        completeness_scores[u.url] = m_completeness[0][int(u.vector)]
        #URL_scores[u.url] = score_url_overlap(query, u.url)
        snippet_scores[u.url] = generic_overlap(query, u.title+' '+u.snippet)
        #print("SNIPPET SCORE",u.url,snippet_scores[u.url])
    return DS_scores, completeness_scores, snippet_scores, posix_scores


def score_pods(query, query_dist, lang):
    '''Score pods for a query'''
    pod_scores = {}
    score_sum = 0.0
    podsum = load_npz(join(pod_dir,'podsum.npz'))
    m_cosines = 1 - distance.cdist(query_dist, podsum.todense(), 'cosine')

    pods = db.session.query(Pods).filter_by(language=lang).filter_by(registered=True).all()
    for p in pods:
        score = m_cosines[0][int(p.DS_vector)]
        print(p.name,score)
        if math.isnan(score):
            score = 0
        pod_scores[p.name] = score
        score_sum += score
    print("POD SCORES:",pod_scores)
    '''If all scores are rubbish, search entire pod collection
    (we're desperate!)'''
    if max(pod_scores.values()) < 0.01:
        return list(pod_scores.keys())
    else:
        best_pods = []
        for k in sorted(pod_scores, key=pod_scores.get, reverse=True):
            if len(best_pods) < 3: 
                print("Appending pod",k)
                best_pods.append(k)
            else:
                break
        return best_pods


def score_docs(query, query_dist, tokenized, kwd):
    '''Score documents for a query'''
    document_scores = {}  # Document scores
    DS_scores, completeness_scores, snippet_scores, posix_scores = score(query, query_dist, tokenized, kwd)
    print("POSIX SCORES",posix_scores)
    for url in list(DS_scores.keys()):
        document_scores[url] = 0.0
        idx = db.session.query(Urls).filter_by(url=url).first().vector
        if idx in posix_scores:
            document_scores[url]+=posix_scores[idx]
        document_scores[url]+=completeness_scores[url]
        document_scores[url]+=snippet_scores[url]
        if snippet_scores[url] == 1:
            document_scores[url]+=1 #bonus points
        if math.isnan(document_scores[url]) or completeness_scores[url] < 0.3:  # Check for potential NaN -- messes up with sorting in bestURLs.
            document_scores[url] = 0
        else:
            print(url, document_scores[url], completeness_scores[url], snippet_scores[url])
    return document_scores


def bestURLs(doc_scores):
    best_urls = []
    netlocs_used = []  # Don't return 100 pages from the same site
    c = 0
    for w in sorted(doc_scores, key=doc_scores.get, reverse=True):
        loc = urlparse(w).netloc
        if c < 50:
            if doc_scores[w] > 0:
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



def output(best_urls, doctype):
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
        results.append(result)
        pod = rec.pod
        if pod not in pods:
            pods.append(pod)
    return results, pods


def run(q, pears):
    max_thread = int(multiprocessing.cpu_count() * 0.5)
    document_scores = {}
    query, doctype, lang = parse_query(q)
    if query == '' and doctype == 'doc':
        urls = db.session.query(Urls).filter_by(pod='Desktop').all()
        best_urls = [u.url for u in urls]
        return output(best_urls, doctype)
    else:
        q_dist, tokenized = compute_query_vectors(query, lang)
        best_pods = score_pods(query, q_dist, lang)
        print("Q:",query,"BEST PODS:",best_pods)
        with Parallel(n_jobs=max_thread, prefer="threads") as parallel:
            delayed_funcs = [delayed(score_docs)(query, q_dist, tokenized, pod) for pod in best_pods]
            scores = parallel(delayed_funcs)
        for dic in scores:
            document_scores.update(dic)
        best_urls = bestURLs(document_scores)
        return output(best_urls, doctype)
