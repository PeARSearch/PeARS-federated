# SPDX-FileCopyrightText: 2024 PeARS Project, <community@pearsproject.org> 
#
# SPDX-License-Identifier: AGPL-3.0-only

from os.path import dirname, join, realpath
import re
from time import time
from math import sqrt
from urllib.parse import urljoin
import requests
import numpy as np
from scipy.spatial import distance
from app import LANGS

dir_path = dirname(realpath(__file__))

def read_language_codes():
    """ Read language code information from static/ling 
    directory. This give mappings between actual language
    codes and the language names used in stopword lists.
    """
    ling_dir = join(dir_path,'static','ling')
    language_codes = {}
    with open(join(ling_dir,'language_codes.txt'),'r', encoding="utf-8") as f:
        for l in f:
            fields = l.rstrip('\n').split(';')
            language_codes[fields[0]] = fields[1]
    return language_codes


def read_stopwords(lang):
    """ Read stopword list for a given language."""
    ling_dir = join(dir_path,'static','ling','stopwords')
    stopwords = []
    with open(join(ling_dir,lang),'r', encoding="utf-8") as f:
        stopwords = f.read().splitlines()
    return stopwords


def _extract_url_info(line):
    """ Helper function. Takes one line from
    the .suggestions file, parse it and return all 
    relevant info (url, theme, language, trigger, 
    contributor). Throws an error if the file has 
    the wrong format.
    """
    try:
        url, kwd, trigger, contributor = line.rstrip('\n').split(';')
        #In case keyword or lang is not given, go back to defaults
        if kwd == '':
            kwd = 'home'
        return url, kwd, trigger, contributor
    except:
        print(">> UTILS: _EXTRACT_URL_INFO: ERROR: .suggestions file does not have the right format.")
        return None


def read_urls(url_file):
    """Read .suggestions file from a particular user.
    The file is located in static/userdata/ and contains
    one URL per line. This parses the line and returns 
    all relevant information for each URL.
    """
    urls = []
    keywords = []
    notes = []
    contributors = []
    errors = False
    with open(url_file, 'r', encoding="utf-8") as fd:
        for line in fd:
            matches = _extract_url_info(line)
            if matches:
                urls.append(matches[0])
                keywords.append(matches[1])
                notes.append(matches[2])
                contributors.append(matches[3])
            else:
                errors = True
    return urls, keywords, notes, contributors, errors

def read_docs(doc_file):
    """ Read document file in <doc></doc> format.
    In PeARS Federated, used to index the information
    provided by users (offline, not on the Web).
    """
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


def normalise(v):
    norm = np.linalg.norm(v)
    if norm == 0:
        return v
    return v / norm


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
        except:
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
        try:
            cos = cosine_similarity(vec, v.vector)
            cosines[k] = cos
        except:
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
    lang = None
    doctype = None
    clean_query = ""
    m = re.search('(.*) -(..\s*)$',query)
    if m:
        query = m.group(1)
        lang = m.group(2)
    words = query.split()
    for w in words:
        if w[0] == '!':
            doctype = w[1:]
        else:
            clean_query+=w+' '
    clean_query = clean_query[:-1]
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

def beautify_snippet(snippet, img, query):
    snippet = snippet.replace('og desc:','')
    if snippet[-3:] != '...':
        snippet+='...'
    tmp_snippet = snippet
    for w in query.split():
        tmp_snippet = tmp_snippet.replace(w,'<b>'+w+'</b>')
        tmp_snippet = tmp_snippet.replace(w.title(),'<b>'+w.title()+'</b>')
    if img != 'None': #None is str in database
        img = join('static','assets',img)
        tmp_snippet = "<img src='"+img+"' style='float:left; width:150px; margin-right: 10px'/>"+tmp_snippet
    return tmp_snippet

def timer(func):
    # This function shows the execution time of
    # the function object passed
    def wrap_func(*args, **kwargs):
        t1 = time()
        result = func(*args, **kwargs)
        t2 = time()
        print(f'\n>>TIMER: Function {func.__name__!r} executed in {(t2-t1):.4f}s')
        return result
    return wrap_func
