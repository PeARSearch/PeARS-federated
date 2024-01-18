# SPDX-FileCopyrightText: 2023 PeARS Project, <community@pearsproject.org>, 
#
# SPDX-License-Identifier: AGPL-3.0-only

from app import vocab, inverted_vocab, logprobs, vectorizer
import numpy as np
from scipy.sparse import csr_matrix, vstack
from sklearn import preprocessing

def read_vocab(vocab_file):
    c = 0
    vocab = {}
    reverse_vocab = {}
    logprobs = []
    with open(vocab_file) as f:
        for l in f:
            l = l.rstrip('\n')
            wp = l.split('\t')[0]
            logprob = -(float(l.split('\t')[1]))
            #logprob = log(lp + 1.1)
            if wp in vocab or wp == '':
                continue
            vocab[wp] = c
            reverse_vocab[c] = wp
            logprobs.append(logprob)
            c+=1
    return vocab, reverse_vocab, logprobs

def wta_vectorized(feature_mat, k, percent=True):
    # thanks https://stackoverflow.com/a/59405060
    m, n = feature_mat.shape
    if percent:
        k = int(k * n / 100)
    # get (unsorted) indices of top-k values
    topk_indices = np.argpartition(feature_mat, -k, axis=1)[:, -k:]
    # get k-th value
    rows, _ = np.indices((m, k))
    kth_vals = feature_mat[rows, topk_indices].min(axis=1)
    # get boolean mask of values smaller than k-th
    is_smaller_than_kth = feature_mat < kth_vals[:, None]
    # replace mask by 0
    feature_mat[is_smaller_than_kth] = 0
    return feature_mat

def encode_docs(doc_list, vectorizer, logprobs, power, top_words):
    logprobs = np.array([logprob ** power for logprob in logprobs])
    X = vectorizer.fit_transform(doc_list)
    X = X.multiply(logprobs)
    X = wta_vectorized(X.toarray(),top_words,False)
    X = csr_matrix(X)
    return X

def read_n_encode_dataset(doc=None, vectorizer=None, logprobs=None, power=None, top_words=None, verbose=False):
    # read
    doc_list = [doc]

    # encode
    X = encode_docs(doc_list, vectorizer, logprobs, power, top_words)
    if verbose:
        k = 10
        inds = np.argpartition(X.todense(), -k, axis=1)[:, -k:]
        for i in range(X.shape[0]):
            ks = [list(vectorizer.vocabulary.keys())[list(vectorizer.vocabulary.values()).index(k)] for k in np.squeeze(np.asarray(inds[i]))]
    return X


def vectorize(lang, text, logprob_power, top_words):
    '''Takes input file and return vectorized /scaled dataset'''
    dataset = read_n_encode_dataset(text, vectorizer, logprobs, logprob_power, top_words)
    dataset = dataset.todense()
    return np.asarray(dataset)

def scale(dataset):
    #scaler = preprocessing.MinMaxScaler().fit(dataset)
    scaler = preprocessing.Normalizer(norm='l2').fit(dataset)
    return scaler.transform(dataset)

def vectorize_scale(lang, text, logprob_power, top_words):
    dataset = vectorize(lang, text, logprob_power,top_words)
    return scale(dataset)
