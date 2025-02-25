from time import time
from urllib.parse import urlparse
import numpy as np
import requests
from requests.exceptions import ConnectionError
from os.path import dirname, realpath, join, exists
from scipy.spatial import distance
from app import app, LANGUAGE_CODES
from app.search.score_pages import compute_query_vectors

base_dir_path = dirname(dirname(dirname(realpath(__file__))))

def get_known_instances():
    known_instances = []
    known_instances_file = join(base_dir_path, '.known_instances.txt')
    if not exists(known_instances_file):
        return known_instances
    with open(known_instances_file, 'r', encoding='utf-8') as f:
        known_instances = f.read().splitlines()
    return known_instances

def filter_instances_by_language():
    ''' Return only instances that match the main language
    of this instance.
    '''
    this_instance_language = list(LANGUAGE_CODES.keys())[0]
    instances = get_known_instances()
    filtered_instances = []
    filtered_matrix = []
    headers = {'User-Agent': app.config['USER-AGENT']}
    for i in instances:

        # make sure that we're not trying to index with ourselves
        if i.rstrip("/") == app.config["SITENAME"].rstrip("/"):
            print(f"WARNING: It seems like you're trying to federate with yourself. Consider removing the name of your local site from .known_hosts.txt if it's on it. For now, I'm skipping this instance ({i}).")
            continue

        resp = None
        url = join(i, 'api', 'languages')
        try:
            resp = requests.get(url, timeout=30, headers=headers)
        except Exception as e:
            print(f"\t>> ERROR: filter_instances_by_language: request failed trying to access {url}; error message {e}")
            continue
        if resp.status_code != 200:
            print(f"\t>> ERROR: filter_instances_by_language: got non-200 status code when trying to access {url}...")    
            continue        
        languages = resp.json()['json_list']
        if this_instance_language not in languages:
            continue

        #print(url, languages, this_instance_language)

        # first get the signature of the instance
        url = join(i, 'api', 'signature', this_instance_language)
        try:
            resp = requests.get(url, timeout=30, headers=headers)
        except Exception as e:
            print(f"\t>> ERROR: filter_instances_by_language: request failed trying to access {url}; error message: {e}")
            continue
        if resp.status_code != 200:
            print(f"\t>> ERROR: filter_instances_by_language: got an error code trying to access {url}...")
            continue

        signature = np.array(resp.json())
        
        # retrieve instance metadata
        identity_info_url = join(i, 'api', 'identity')
        try:
            identity_info = requests.get(identity_info_url, timeout=30, headers=headers).json()
            identity_info["url"] = i
        except Exception as e:
            print(f"\t>> ERROR: filter_instances_by_language: request failed trying to access {identity_info_url}, error message: {e}")
            identity_info = {
                "url": i,
                "sitename": urlparse(i).hostname,
                "site_topic": None,
                "organization": None
            }

        filtered_instances.append(identity_info)
        filtered_matrix.append(signature)
    filtered_matrix = np.array(filtered_matrix)
    return filtered_instances, filtered_matrix


def get_best_instances(query, lang, instances, m, top_k=3):
    q_tokenized, extended_q_tokenized, q_vectors, extended_q_vectors = compute_query_vectors(query, lang, expansion_length=10)
    query_vector = np.sum(q_vectors, axis=0)
    
    # Only compute cosines over the dimensions of interest
    a = np.where(query_vector!=0)[1]
    cos = 1 - distance.cdist(query_vector[:,a], m[:,a], 'cosine')[0]
    cos[np.isnan(cos)] = 0

    # Instance ids with non-zero values (match at least one subword)
    idx = np.where(cos!=0)[0]

    # Sort instance ids with non-zero values
    idx = np.argsort(cos)[-len(idx):][::-1][:50]

    # Get instances
    document_scores = {}
    best_instances = [instances[i] for i in idx][:top_k]
    print("BEST INSTANCES", [i["url"] for i in best_instances])

    return best_instances


def get_cross_instance_results(query, instances):
    from app import M
    best_instances = get_best_instances(query, 'en', instances, M, top_k=2)
    results = {}
    headers = {'User-Agent': app.config['USER-AGENT']}
    for i in best_instances:
        url = join(i["url"], 'api', 'search?q='+query)
        try:
            t_before = time()
            resp = requests.get(url, timeout=30, headers=headers)
            t_after = time()
            t_delta = t_after - t_before
            print(f"Request to remote instance (url={url}) took {t_delta:.3f}s")
        except Exception as e:
            print(f"Error when connecting to {url}, error message: {e}")
            r = {}

        if resp.status_code == 200:
            json_result = resp.json()['json_list']
            # legacy code for older instances
            if type(json_result) is list:
                r = json_result[1]
            # up-to-date instances
            else:
                r = json_result
        else:
            print(f"Got non-200 status code from {url}")
            r = {}

        for url, d in r.items():
            r[url]["x_instance_info"] = i
            # The following is only temporary until all instances have been updated to return page scores
            if 'score' not in d:
                if any(w in d['title'] for w in query.lower().split()) or any(w in d['snippet'].lower() for w in query.lower().split()):
                    r[url]['score'] = 2
                else:
                    r[url]['score'] = 0
        results.update(r)
    return results
