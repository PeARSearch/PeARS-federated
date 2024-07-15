# SPDX-FileCopyrightText: 2022 PeARS Project, <community@pearsproject.org>, 
#
# SPDX-License-Identifier: AGPL-3.0-only

import logging
from os.path import dirname, join, realpath
from os import getenv
import numpy as np
from scipy.sparse import csr_matrix, vstack, save_npz, load_npz
from app import models, VEC_SIZE, DEFAULT_PATH
from app.api.models import sp
from app.indexer.htmlparser import extract_html
from app.indexer.pdfparser import extract_txt
from app.indexer.vectorizer import vectorize_scale
from app.utils import timer
from app.utils_db import create_pod_npz_pos

dir_path = dirname(dirname(realpath(__file__)))
pod_dir = getenv("PODS_DIR", join(dir_path, 'pods'))

def tokenize_text(text, lang, stringify = True):
    """ Load the SentencePiece model included in the install
    and tokenize the given text.

    Arguments: the text to be tokenized.
    """
    sp.load(join(DEFAULT_PATH, f'api/models/{lang}/{lang}wiki.16k.model'))
    tokens = [wp for wp in sp.encode_as_pieces(text.lower())]
    if stringify:
        text = ' '.join([wp for wp in sp.encode_as_pieces(text.lower())])
        #print("TOKENIZED",text)
        #print([(t, logprobs[vocab[t]]) for t in text.split()])
        return text
    return tokens


def compute_and_stack_new_vec(lang, tokenized_text, pod_m):
    """ Given the tokenized text, compute a new vector
    and stack it onto the existing matrix for that pod.
    """
    v = vectorize_scale(lang, tokenized_text, 5, VEC_SIZE) #log prob power 5
    if np.sum(v) != 0:
        logging.debug(f"compute_and_stack_new_vec 1 {pod_m.shape[0]}")
        pod_m = vstack((pod_m,csr_matrix(v)))
        logging.debug(f"compute_and_stack_new_vec 2 {pod_m.shape[0]}")
        return pod_m, True
    return pod_m, False


def compute_vector(url, theme, contributor, url_type):
    """ Compute vector for target URL. This includes retrieving the
    page, extracting the title and text from it, and adding the 
    document vector to the matrix for the user's chosen theme.
    """
    print("Computing vector for", url, "(",theme,")")
    messages = []
    print("CONTENT TYPE",url_type)
    if 'text/html' in url_type:
        title, body_str, lang, snippet, cc, error = extract_html(url)
    elif 'application/pdf' in url_type:
        title, body_str, lang, snippet, cc, error = extract_txt(url, contributor)
    else:
        error = ">> INDEXER: MK_PAGE_VECTORS: ERROR: compute_vectors: No supported content type."
    if error is None:
        logging.info(f"TITLE {title} SNIPPET {snippet} CC {cc} ERROR {error}")
        create_pod_npz_pos(contributor, theme, lang)
        user_dir = join(pod_dir, contributor, lang)
        npz_path = join(user_dir,theme+'.u.'+contributor+'.npz')
        pod_m = load_npz(npz_path)
        text = title + " " + body_str
        tokenized_text = tokenize_text(text, lang)
        pod_m, success = compute_and_stack_new_vec(lang, tokenized_text, pod_m)
        if success:
            save_npz(npz_path,pod_m)
            vid = pod_m.shape[0]
            return True, tokenized_text, lang, title, snippet, vid, messages
    messages.append(">> INDEXER ERROR: compute_vectors: error during parsing")
    return False, None, None, None, None, None, messages


def compute_vector_local_docs(title, doc, theme, lang, contributor):
    """ Compute vector for manual document and add it to the matrix
    for the user's chosen theme.
    """
    npz_path = join(pod_dir,contributor, lang, theme+'.u.'+contributor+'.npz')
    pod_m = load_npz(npz_path)
    #print("Computing vectors for", target_url, "(",theme,")",lang)
    text = title + ". " + theme + ". " + doc
    text = tokenize_text(text, lang)
    pod_m, success = compute_and_stack_new_vec(lang, text, pod_m)
    if doc != "":
        snippet = doc[:500]+'...'
    else:
        snippet = title
    if success:
        save_npz(npz_path,pod_m)
        vid = pod_m.shape[0]
        return True, text, snippet, vid
    return False, text, snippet, None

def compute_query_vectors(query, lang, expansion_length=None):
    """ Make query vectors: the vector for the original
    query as well as the vector for the expanded query.
    This involves tokenization, query expansion using 
    pre-computed wordpiece neighbours from a FastText 
    model and vectorizing.
    """
    print("QUERY LANG",lang)
    nns = models[lang]['nns']
    words = query.split()
    print("QUERY SPLIT:",words)

    # Individual words tokenized
    words_tokenized = []
    for w in words:
        words_tokenized.append(tokenize_text(w, lang, stringify=False))
    print("WORDS TOKENIZED:",words_tokenized)

    # Add similar tokens
    words_tokenized_expanded = []
    for w in words_tokenized:
        sims = [i for i in w if len(i) > 1]
        for wtoken in w:
            if len(wtoken.replace('▁','')) > 3:
                if wtoken not in nns:
                    continue
                if expansion_length:
                    neighbours = [n for n in nns[wtoken] if len(n) > 2][:expansion_length]
                else:
                    neighbours = [n for n in nns[wtoken] if len(n) > 2]
                sims.extend(neighbours)
        sims = list(set(sims))
        words_tokenized_expanded.append(sims)
    print("WORDS TOKENIZED EXPANDED:",words_tokenized_expanded)
    logging.debug(f"WORDS TOKENIZED EXPANDED {words_tokenized_expanded}")

    v_query = []
    for w in words_tokenized:
        v_query.append(vectorize_scale(lang, ' '.join(w), 5, len(w))) #log prob power 5
    v_query_expanded = [] # A list of neighbourhood vectors, one for each word in the query
    for nns in words_tokenized_expanded:
        v_query_expanded.append(vectorize_scale(lang, ' '.join(nns), 5, len(nns)))
    #print(csr_matrix(v))
    return words_tokenized, words_tokenized_expanded, v_query, v_query_expanded
