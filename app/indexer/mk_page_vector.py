# SPDX-FileCopyrightText: 2022 PeARS Project, <community@pearsproject.org>, 
#
# SPDX-License-Identifier: AGPL-3.0-only

import re
import numpy as np
import string
from app import db, ftcos, VEC_SIZE, SPM_DEFAULT_MODEL_PATH
from app.api.models import Urls, installed_languages, sp
from app.indexer.htmlparser import extract_html
from app.indexer.pdfparser import extract_txt
from app.indexer.vectorizer import vectorize_scale
from app.utils import convert_to_string, convert_dict_to_string, normalise
from scipy.sparse import csr_matrix, vstack, save_npz, load_npz
from os.path import dirname, join, realpath, isfile


dir_path = dirname(dirname(realpath(__file__)))
pod_dir = join(dir_path,'static','pods')

def tokenize_text(lang, text):
    sp.load(SPM_DEFAULT_MODEL_PATH)
    tokens = [wp for wp in sp.encode_as_pieces(text.lower())]
    text = ' '.join([wp for wp in sp.encode_as_pieces(text.lower())])
    #print("TOKENIZED",text)
    return text


def compute_vec(lang, text, pod_m):
    v = vectorize_scale(lang, text, 5, VEC_SIZE) #log prob power 5, top words 100
    pod_m = vstack((pod_m,csr_matrix(v)))
    return pod_m


def compute_vectors(target_url, keyword, lang, trigger, contributor, url_type):
    print("Computing vectors for", target_url, "(",keyword,")",lang)
    if not db.session.query(Urls).filter_by(url=target_url).all():
        u = Urls(url=target_url)
        print("CONTENT TYPE",url_type)
        if 'text/html' in url_type:
            title, body_str, snippet, cc, error = extract_html(target_url)
        elif 'application/pdf' in url_type:
            title, body_str, snippet, cc, error = extract_txt(target_url)
        else:
            snippet = ''
            error = "ERROR: No supported content type."
        if error is None and snippet != '':
            print("TITLE",title,"SNIPPET",snippet,"CC",cc,"ERROR",error)
            pod_m = load_npz(join(pod_dir,keyword+'.npz'))
            text = title + " " + body_str
            text = tokenize_text(lang, text)
            #print(text)
            pod_m = compute_vec(lang, text, pod_m)
            u.title = str(title)
            u.vector = str(pod_m.shape[0]-1)
            u.keyword = keyword
            u.pod = keyword
            u.snippet = str(snippet)
            u.doctype = 'url'
            u.trigger = trigger
            if contributor != '':
                u.contributor = '@'+contributor
            else:
                u.contributor = contributor
            #print(u.url,u.title,u.vector,u.snippet,u.pod)
            db.session.add(u)
            db.session.commit()
            save_npz(join(pod_dir,keyword+'.npz'),pod_m)
            podsum = np.sum(pod_m, axis=0)
            return True, podsum, text, u.vector
        else:
            if snippet == '':
                print("IGNORING URL: Snippet empty.")
            else:
                print('ERROR DURING PARSING',error)
            return False, None, None, None
    else:
        return False, None, None, None


def compute_vectors_local_docs(target_url, doctype, title, doc, keyword, lang):
    cc = False
    pod_m = load_npz(join(pod_dir,keyword+'.npz'))
    if not db.session.query(Urls).filter_by(url=target_url).all():
        print("Computing vectors for", target_url, "(",keyword,")",lang)
        u = Urls(url=target_url)
        text = title + " " + doc
        text = tokenize_text(lang, text)
        pod_m = compute_vec(lang, text, pod_m)
        u.title = str(title)
        u.vector = str(pod_m.shape[0]-1)
        u.keyword = keyword
        u.pod = keyword
        if doc != "":
            u.snippet = doc[:500]+'...'
        else:
            u.snippet = u.title
        u.doctype = doctype
        print(u.url,u.doctype,u.title,u.vector,u.snippet,u.pod)
        db.session.add(u)
        db.session.commit()
        save_npz(join(pod_dir,keyword+'.npz'),pod_m)
        podsum = np.sum(pod_m, axis=0)
        return True, podsum, text, u.vector
    else:
        return False, None, None, None



def compute_query_vectors(query, lang):
    """ Make distribution for query """
    #query = query.rstrip('\n')
    words = query.split()
    print("QUERY SPLIT:",words)

    # Individual words tokenized
    words_tokenized = []
    for w in words:
        words_tokenized.append(tokenize_text(lang,w))
    print("WORDS TOKENIZED:",words_tokenized)

    # Entire query tokenized
    query_tokenized = ' '.join(words_tokenized)
    print("QUERY TOKENIZED:",query_tokenized)

    # Add similar tokens
    words_tokenized_expanded = []
    for w in words_tokenized:
        sims = [i for i in w.split() if len(i) > 1]
        for wtoken in w.split():
            if len(wtoken.replace('▁','')) > 3:
                neighbours = [n for n in ftcos[wtoken] if len(n) > 2]
                sims.extend(neighbours)
        sims = list(set(sims))
        words_tokenized_expanded.append(sims)
    print("WORDS TOKENIZED EXPANDED",words_tokenized_expanded)

    v_query = vectorize_scale(lang, query_tokenized, 5, len(query_tokenized)) #log prob power 5
    v_query_expanded = [] # A list of neighbourhood vectors, one for each word in the query
    for nns in words_tokenized_expanded:
        v_query_expanded.append(vectorize_scale(lang, ' '.join(nns), 5, len(nns)))
    #print(csr_matrix(v))
    return query_tokenized, words_tokenized_expanded, v_query, v_query_expanded
