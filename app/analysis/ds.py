import sys
import joblib
from glob import glob
from os.path import join, dirname, realpath
from scipy.sparse import csr_matrix
from scipy.sparse.linalg import svds
from scipy.spatial.distance import cdist
import numpy as np
from app import vocab, inverted_vocab
from app.indexer.posix import load_posix


def print_posix(name):
    posix = load_posix(name)
    for i in range(len(posix)):
        w = inverted_vocab[i]
        k = posix[i]
        if len(k) > 0:
            print(w, k)
            docs = []
            for d,p in k.items():
                docs.append(d)
            print(docs)
            inverted_index.append(docs)

def mk_term_doc_m(posindex):
    num_docs = 0
    for i in range(len(posindex)):
        docs = [int(doc) for doc in list(posindex[i].keys())]
        if len(docs) > 0:
            num_docs = max(num_docs,max(docs))
    #print(num_docs)

    term_doc_m = np.zeros((len(vocab),num_docs))

    for i in range(len(posindex)):
        docs = list(posindex[i].keys())
        if len(docs) > 0:
            docs = [int(doc)-1 for doc in docs]
            term_doc_m[i][docs] = 1
    if term_doc_m.size > 0:
        return term_doc_m
    else:
        return None

def mk_doc_term_l(term_doc_m):
    ''' Make list of docs with the terms that occur in each'''
    if term_doc_m is None:
        return None
    doc_term_m = term_doc_m.T
    doc_term_l = []
    for i in range(doc_term_m.shape[0]):
        words = np.where(doc_term_m[i]>0)[0]
        if len(words) > 0:
            #print([inverted_vocab[w] for w in words])
            doc_term_l.append(words)
    return doc_term_l


def update_cooc_m(posindex, cooc_m, doc_term_l, wsize):
    for i in range(len(doc_term_l)):
        doc_terms = doc_term_l[i] 
        #print("\n\nDOC",doc_terms)
        positions = []
        for term in doc_terms: #for each term in doc
            posix_row = posindex[term]
            doc_id = str(i+1) # document ids start at 1
            if doc_id in posix_row:
                ps = [int(p) for p in posix_row[doc_id].split('|')]
                positions.append(ps) #find its positions in that doc

        for i in range(len(positions)):
            for target in positions[i]:
                r = list(range(target-wsize,target+wsize+1))
                for j in range(i+1,len(positions)):
                    for context in positions[j]:
                        if context in r:
                            t_i = doc_terms[i]
                            t_j = doc_terms[j]
                            cooc_m[t_i][t_j]+=1
                            cooc_m[t_j][t_i]+=1
                            #print("cooc",inverted_vocab[t_i], inverted_vocab[t_j], cooc_m[t_i][t_j])

        return cooc_m


def weigh(m):
    """Return a ppmi-weighted CSR sparse matrix from an input CSR matrix."""
    m = csr_matrix(m)
    words = csr_matrix(m.sum(axis=1))
    contexts = csr_matrix(m.sum(axis=0))
    total_sum = m.sum()
    m = m.multiply(words.power(-1))\
                           .multiply(contexts.power(-1))\
                           .multiply(total_sum)
    m.data = np.log2(m.data)  # PMI = log(#(w, c) * D / (#w * #c))
    m = m.multiply(m > 0)  # PPMI
    m.eliminate_zeros()
    return m

def apply_sparse_svd(M, dim):
    """Apply SVD to sparse CSR matrix."""
    if dim == 0 or dim >= min(M.shape):
        print('Specified k={} null or exceeds matrix shape limit = {}. Resetting k to {}'.format(dim, min(M.shape), min(M.shape) - 1))
        dim = min(M.shape) - 1
    U, S, _ = svds(M, k=dim, which='LM', return_singular_vectors='u')
    S = S[::-1]  # put singular values in decreasing order of values
    U = U[:, ::-1]  # put singular vectors in decreasing order of sing. values
    return U, S

def compute_highest_ppmis(m, top_words=1000, k=10):
    m = m.todense()
    m = m[:top_words,:]
    print(m.shape)
    mvocab = list(vocab.keys())[:top_words]
    tops = {}
    for i in range(len(mvocab)):
        word = mvocab[i]
        ns = []
        target_ppmis = np.squeeze(np.asarray(m[i]))
        if sum(target_ppmis) > 0:
            best_n = np.argpartition(target_ppmis, -k)[-k:]
            for ind in best_n:
                if target_ppmis[ind] > 0 and ind != word:
                    ns.append(inverted_vocab[ind])
            tops[word] = ns

    return tops


def compute_nns(m, top_words=1000, k=10):
    m = m[:top_words,:]
    mvocab = list(vocab.keys())[:top_words]
    cosines = 1 - cdist(m, m, metric="cosine")

    nns = {}
    for i in range(len(mvocab)):
        word = mvocab[i]
        ns = []
        target_cosines = cosines[i]
        best_n = np.argpartition(target_cosines, -k)[-k:]

        for ind in best_n:
            if ind != word:
                ns.append(mvocab[ind])
        nns[word] = ns

    return nns


def analyse_ppmis(input_dir, wsize=3):
    cooc_m = np.zeros((len(vocab), len(vocab)))
    print(input_dir)
    fs = glob(join(input_dir,'*.pos'))
    print(fs)

    for f in fs:
        print(f)
        posindex = load_posix(f.replace('.pos',''))

        term_doc_m = mk_term_doc_m(posindex)
        #print("term_doc_m",term_doc_m)
        doc_term_l = mk_doc_term_l(term_doc_m)
        if doc_term_l is not None:
            #print("doc_term_l",len(doc_term_l))
            cooc_m = update_cooc_m(posindex, cooc_m, doc_term_l, wsize)
            #print("cooc_m", cooc_m)

    print(">> INFO: ANALYSIS: DS: analyse_ppmis: num coocurrences",np.sum(cooc_m))

    weighted_m = weigh(cooc_m)
    #print("weighted_m", weighted_m)
    #print("dim", weighted_m.shape)

    tops = compute_highest_ppmis(weighted_m, top_words=len(vocab))
    return tops
    #for w, ppmis in tops.items():
    #    print(w,ppmis)

    #reduced_m, singular_values = apply_sparse_svd(weighted_m, 100)
    #print("reduced_m", reduced_m)

    #nns = compute_nns(reduced_m, top_words=1000)
    #for w, nn in nns.items():
#    print(w,nn)
