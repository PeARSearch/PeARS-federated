# SPDX-FileCopyrightText: 2023 PeARS Project, <community@pearsproject.org> 
#
# SPDX-License-Identifier: AGPL-3.0-only

import joblib
import logging
import re
import requests

from bs4 import BeautifulSoup
from math import sqrt
import numpy as np
from urllib.parse import urljoin
from scipy.spatial import distance
from scipy.sparse import csr_matrix, save_npz
from os.path import dirname, join, realpath, isfile
from pathlib import Path
from app import VEC_SIZE, LANG, vocab

dir_path = dirname(realpath(__file__))

def read_language_codes():
    dir_path = dirname(dirname(realpath(__file__)))
    ling_dir = join(dir_path,'app','static','ling')
    LANGUAGE_CODES = {}
    with open(join(ling_dir,'language_codes.txt'),'r') as f:
        for l in f:
            fields = l.rstrip('\n').split(';')
            LANGUAGE_CODES[fields[0]] = fields[1]
    return LANGUAGE_CODES

def read_stopwords(lang):
    dir_path = dirname(dirname(realpath(__file__)))
    ling_dir = join(dir_path,'app','static','ling','stopwords')
    STOPWORDS = []
    with open(join(ling_dir,lang),'r') as f:
        STOPWORDS = f.read().splitlines()
    return STOPWORDS


def _extract_url_and_kwd(line):
    try:
        url, kwd, lang, trigger, contributor = line.rstrip('\n').split(';')
        #In case keyword or lang is not given, go back to defaults
        if kwd == '':
            kwd = 'home'
        if lang == '':
            lang = LANG
        return url, kwd, lang, trigger, contributor
    except:
        print("ERROR: urls_to_index.txt does not have the right format.")
        return None


def readUrls(url_file):
    urls = []
    keywords = []
    langs = []
    triggers = []
    contributors = []
    errors = False
    with open(url_file) as fd:
        for line in fd:
            matches = _extract_url_and_kwd(line)
            if matches:
                urls.append(matches[0])
                keywords.append(matches[1])
                langs.append(matches[2])
                triggers.append(matches[3])
                contributors.append(matches[4])
            else:
                errors = True
    return urls, keywords, langs, triggers, contributors, errors

def readDocs(doc_file):
    urls = []
    with open(doc_file) as df:
        for l in df:
            l=l.rstrip('\n')
            if l[:4] == "<doc":
                m = re.search('url=\"([^\"]*)\"',l)
                url = m.group(1)
            elif "</doc" not in l:
                continue
            else:
                urls.append(url)
    return urls


def readBookmarks(bookmark_file, keyword):
    print("READING BOOKMARKS")
    urls = []
    bs_obj = BeautifulSoup(open(bookmark_file), "html.parser")
    dt = bs_obj.find_all('dt')
    tag =''
    for i in dt:
        n = i.find_next()
        if n.name == 'h3':
            tag = n.text
            continue
        else:
            if tag.lower() == keyword.lower():
                print(f'url = {n.get("href")}')
                print(f'website name = {n.text}')
                urls.append(n.get("href"))
    return urls


def readPods(pod_file):
    pods = []
    f = open(pod_file, 'r')
    for line in f:
        line = line.rstrip('\n')
        pods.append(line)
    f.close()
    return pods


def init_pod(pod_name):
    dir_path = dirname(dirname(realpath(__file__)))
    pod_dir = join(dir_path,'app', 'static','pods')
    if not isfile(join(pod_dir,pod_name+'.npz')):
        print("Making 0 CSR matrix for new pod")
        pod = np.zeros((1,VEC_SIZE))
        pod = csr_matrix(pod)
        save_npz(join(pod_dir,pod_name+'.npz'), pod)
    
    if not isfile(join(pod_dir,pod_name+'.pos')):
        print("Making empty positional index for new pod")
        posindex = [{} for _ in range(len(vocab))]
        joblib.dump(posindex, join(pod_dir,pod_name+'.pos'))

def init_podsum():
    dir_path = dirname(dirname(realpath(__file__)))
    pod_dir = join(dir_path,'app','static','pods')
    Path(pod_dir).mkdir(exist_ok=True, parents=True)
    print("Making 0 CSR matrix for pod summaries")
    print("POD DIR",pod_dir)
    pod_summaries = np.zeros((1,VEC_SIZE))
    pod_summaries = csr_matrix(pod_summaries)
    save_npz(join(pod_dir,"podsum.npz"), pod_summaries)


def normalise(v):
    norm = np.linalg.norm(v)
    if norm == 0:
        return v
    return v / norm


def convert_to_string(vector):
    s = ' '.join(str(i) for i in vector)
    return(s)


def convert_to_array(vector):
    # for i in vector.rstrip(' ').split(' '):
    #    print('#',i,float(i))
    return np.array([float(i) for i in vector.split()])


def convert_dict_to_string(dic):
    s = ""
    for k, v in dic.items():
        s += k + ':' + str(v) + ' '
    return s


def convert_string_to_dict(s):
    d = {}
    els = s.rstrip(' ').split()
    for e in els:
        if ':' in e:
            pair = e.split(':')
            if pair[0] != "" and pair[1] != "":
                d[pair[0]] = pair[1]
    return d


def cosine_similarity(v1, v2):
    if len(v1) != len(v2):
        return 0.0
    num = np.dot(v1, v2)
    den_a = np.dot(v1, v1)
    den_b = np.dot(v2, v2)
    return num / (sqrt(den_a) * sqrt(den_b))

def hamming_similarity(v1, v2):
    return 1 - distance.hamming(v1,v2)

def cosine_to_matrix(q, M):
    qsqrt = sqrt(np.dot(q, q))
    if qsqrt == 0:
        return np.zeros(M.shape[0])
    qMdot = np.dot(q, M.T)
    Mdot = np.dot(M, M.T)
    Msqrts = [sqrt(Mdot[i][i]) for i in range(len(Mdot[0]))]
    cosines = []
    for i in range(len(Mdot[0])):
        if Msqrts[i] != 0:
            cosines.append(qMdot[i] / (qsqrt * Msqrts[i]))
        else:
            cosines.append(0)
    return cosines


def sim_to_matrix(dm_dict, vec, n):
    cosines = {}
    c = 0
    for k, v in dm_dict.items():
        try:
            cos = cosine_similarity(vec, v)
            cosines[k] = cos
            c += 1
        except Exception:
            pass
    c = 0
    neighbours = []
    for t in sorted(cosines, key=cosines.get, reverse=True):
        if c < n:
            if t.isalpha():
                print(t, cosines[t])
                neighbours.append(t)
                c += 1
        else:
            break
    return neighbours


def sim_to_matrix_url(url_dict, vec, n):
    cosines = {}
    for k, v in url_dict.items():
        logging.exception(v.url)
        try:
            cos = cosine_similarity(vec, v.vector)
            cosines[k] = cos
        except Exception:
            pass
    c = 0
    neighbours = []
    for t in sorted(cosines, key=cosines.get, reverse=True):
        if c < n:
            # print(t,cosines[t])
            neighbour = [t, url_dict[t].title, url_dict[t].snippet]
            neighbours.append(neighbour)
            c += 1
        else:
            break
    return neighbours


def get_pod_info(url):
    print("Fetching pod", urljoin(url, "api/self/"))
    pod = None
    try:
        r = requests.get(urljoin(url, "api/self/"))
        if r.status_code == 200:
            pod = r.json()
    except Exception:
        print("Problem fetching pod...")
    return pod


def parse_query(query):
    lang = LANG #default
    doctype = None
    clean_query = ""
    m = re.search('(.*) -(..\s*)$',query)
    if m:
        query = m.group(1)
        lang = m.group(2)
    words = query.split()
    for w in words:
        if w[0] == '?':
            doctype = 'ind'
            clean_query+=w[1:]+' '
        elif w[0] == '!':
            doctype = w[1:]
        else:
            clean_query+=w+' '
    clean_query = clean_query[:-1]
    if query.strip() == '/': #FIX
        doctype = 'doc'
    print(clean_query, doctype)
    return clean_query, doctype, lang



def beautify_title(title, doctype):
    if doctype == 'stat':
        title = '📈 '+title
    if doctype == 'doc':
        title = '📝 '+title
    if doctype == 'url':
        title = '🌏 '+title
    if doctype == 'ind':
        title = '☺️  '+title
    if doctype == 'map':
        title = '📍 '+title
    return title

def beautify_snippet(snippet, img, query, expert):
    snippet = snippet.replace('og desc:','')
    if snippet[-3:] != '...':
        snippet+='...'
    tmp_snippet = snippet
    for w in query.split():
        tmp_snippet = tmp_snippet.replace(w,'<b>'+w+'</b>')
        tmp_snippet = tmp_snippet.replace(w.title(),'<b>'+w.title()+'</b>')
    if img:
        if expert:
            img = join('..','..','..','static','assets',img)
        else:
            img = join('static','assets',img)
        tmp_snippet = "<img src='"+img+"' style='float:left; width:150px; margin-right: 10px'/>"+tmp_snippet
    return tmp_snippet
