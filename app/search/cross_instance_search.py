import numpy as np
import requests
from os.path import dirname, realpath, join, exists
from app import app, LANGUAGE_CODES

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
    this_instance_language = list(LANGUAGE_CODES.keys())[0]
    instances = get_known_instances()
    filtered_instances = {}
    headers = {'User-Agent': app.config['USER-AGENT']}
    for i in instances:
        resp = None
        url = join(i, 'api', 'languages')
        try:
            resp = requests.get(url, timeout=30, headers=headers)
        except Exception:
            print(f"\t>> ERROR: filter_instances_by_language: request failed trying to access {url}...")
            continue
        languages = resp.json()['json_list']
        if this_instance_language not in languages:
            continue

        print(url, languages, this_instance_language)

        url = join(i, 'api', 'signature', this_instance_language)
        try:
            resp = requests.get(url, timeout=30, headers=headers)
        except Exception:
            print(f"\t>> ERROR: filter_instances_by_language: request failed trying to access {url}...")
            continue
        signature = np.array(resp.json())
        print(signature)
        filtered_instances[i] = signature
    return filtered_instances

def get_cross_instance_results(query, instances):
    results = {}
    headers = {'User-Agent': app.config['USER-AGENT']}
    for i in instances:
        url = join(i, 'api', 'search?q='+query)
        resp = requests.get(url, timeout=30, headers=headers)
        r = resp.json()
        results.update(r)
    return results
