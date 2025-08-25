# SPDX-FileCopyrightText: 2024 PeARS Project, <community@pearsproject.org>, 
#
# SPDX-License-Identifier: AGPL-3.0-only

import re
import requests
from shutil import copy2, copytree
from os import remove
from os.path import dirname, realpath, join, exists
from os import getenv
from glob import glob
from datetime import datetime
from pathlib import Path
from random import shuffle
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import numpy as np
import joblib
from flask import Blueprint
import click
from werkzeug.security import generate_password_hash
from scipy.sparse import load_npz, csr_matrix, vstack
from app.indexer.controllers import run_indexer_url, index_doc_from_cli
from app.indexer.access import request_url
from app.indexer.posix import load_posix
from app.indexer.htmlparser import extract_links
from app.orchard.mk_urls_file import get_reindexable_pod_for_admin
from app import db, User, Urls, Pods, VEC_SIZE

pears = Blueprint('pears', __name__)

dir_path = dirname(dirname(dirname(realpath(__file__))))
pod_dir = getenv("PODS_DIR", join(dir_path, 'app','pods'))
user_dir = getenv("SUGGESTIONS_DIR", join(dir_path, 'app','userdata'))


###############################
# ADMIN USER AND APP MANAGEMENT
###############################

@pears.cli.command('setadmin')
@click.argument('username')
def set_admin(username):
    '''Use from CLI with flask pears setadmin <username>.'''
    user = User.query.filter_by(username=username).first()
    user.is_admin = True
    db.session.commit()
    print(username,"is now admin.")

@pears.cli.command('create-user')
@click.argument('username')
@click.argument('password')
@click.argument('email')
def create_user(username, password, email):
    '''
    Creates a user with provided username, password and email.
    This user is not admin and their email address is automatically confirmed.
    '''
    user = User(username=username,
                password=generate_password_hash(password, method='scrypt'),
                email=email,
                is_confirmed=True,
                confirmed_on=datetime.now())
    db.session.add(user)
    db.session.commit()
    print(username, "has been registered.")

@pears.cli.command('print-users')
def print_users():
    '''
    Print users on this instance.
    '''
    users = User.query.all()
    print("\n## USER LIST ##")
    for u in users:
        print(u.username, u.email, u.is_confirmed, u.is_admin)

@pears.cli.command('install-language')
@click.argument('lang')
def install_language(lang):
    local_dir = join(dir_path, "app", "api", "models", lang)
    Path(local_dir).mkdir(exist_ok=True, parents=True)

    # The repository for pretrained models
    model_path = 'https://github.com/possible-worlds-research/pretrained-tokenizers/tree/main/models'

    # this will load the bare page - without the file list
    # we'll just use this to get the cookies so we can spoof the AJAX request that gets the file list
    req_bare_page = requests.get(model_path, allow_redirects=True)
    
    file_list_url = model_path.replace("/tree/", "/tree-commit-info/")
    req_files = requests.get(
        url=file_list_url,
        cookies=req_bare_page.cookies,
        headers={
            "Accept": "application/json",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "en-US,en;q=0.5",
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Github-Verified-Fetch": "true",
            "Host": "github.com",
            "Pragma": "no-cache",
            "Priority": "u=4",
            "Referer": model_path,
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "Sec-GPC": "1",
            "TE": "trailers",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:141.0) Gecko/20100101 Firefox/141.0"
        }
    )
    model_file_dict = req_files.json()
    date = "0000-00-00"
    for model_file in model_file_dict:
        m = re.search(lang+'wiki.16k.*model', model_file)
        if m:
            date = m.group(0).replace(lang+'wiki.16k.','').replace('.model','')
            break

    repo_path = 'https://github.com/possible-worlds-research/pretrained-tokenizers/blob/main/'
    paths = ['models/'+lang+'wiki.16k.'+date+'.model', 'vocabs/'+lang+'wiki.16k.'+date+'.vocab', 'nns/'+lang+'wiki.16k.'+date+'.cos']

    for p in paths:
        path = join(repo_path, p+'?raw=true')
        filename = p.split('/')[-1].replace(date+'.','')
        local_file = join(local_dir,filename)
        print("Downloading",path,"to",local_file,"...")
        try:
            with open(local_file,'wb') as f:
                f.write(requests.get(path,allow_redirects=True).content)
        except Exception:
            print("Request failed when trying to access", path, "...")



###########################
# DIAGNOSES
###########################

@pears.cli.command('diagnose')
def diagnose():
    from app.cli.diagnose import check_sitename
    check_sitename()


###########################
# BACKUP STUFF
###########################

@pears.cli.command('exporturls')
def export_urls():
    '''Get all URLs on this instance'''
    date = datetime.now().strftime('%Y-%m-%d-%Hh%Mm')
    filepath = join(user_dir,"admin."+date+".pears.txt")
    urls = []
    pods = Pods.query.all()
    for pod in pods:
        name = pod.name.split('.u.')[0]
        urls.extend(get_reindexable_pod_for_admin(name))
    with open(filepath, 'w', encoding='utf-8') as f:
        for url in urls:
            f.write(url+'\n')


@pears.cli.command('legacyexporturls')
@click.argument('user')
def legacy_export_urls(user):
    '''Get all URLs on this instance'''
    urls = Urls.query.all()
    for u in urls:
        print(u.url+';'+u.pod+';;'+user)


@pears.cli.command('backup')
@click.argument('backupdir')
def backup(backupdir):
    '''Backup database and pods to specified directory'''
    #Check if directory exists, otherwise create it
    Path(backupdir).mkdir(parents=True, exist_ok=True)
    #Get today's date
    date = datetime.now().strftime('%Y-%m-%d-%Hh%Mm')
    dirpath = join(backupdir,'pears-'+date)
    Path(dirpath).mkdir(parents=True, exist_ok=True)
    #Copy database
    copy2('app.db',dirpath)
    #Copy pods folder
    copytree(pod_dir, join(dirpath,'pods'))


#########################
# ADMIN INDEXING TOOLS
#########################

@pears.cli.command('index')
@click.argument('host_url')
@click.argument('filepath')
def index(host_url, filepath):
    '''
    Index from a manual created URL file.
    The file should have the following information,
    separated by semi-colons:
    url; theme; lang; note; contributor
    with one url per line.
    Use from CLI with flask pears index <your site's domain> <path>
    '''
    # make sure the host_url starts with https:// so that it can be parsed correctly by urllib.parse.urlparse 
    if not host_url.startswith("https://"):
        host_url = "https://" + host_url

    users = User.query.all()
    for user in users:
        Path(join(pod_dir,user.username)).mkdir(parents=True, exist_ok=True)
    with open(filepath, encoding="utf-8") as f:
        for line in f:
            m = re.match(r"^(.+?);(.+?);;(.+?)$", line)
            assert m, "URL file is not formatted correctly!"
            url = m.group(1)
            pod = m.group(2)
            user = m.group(3)
            run_indexer_url(url, pod, None, user, host_url)


@pears.cli.command('randomcrawl')
@click.argument('n')
@click.argument('username')
def random_crawl(n, username):
    '''Randomly crawl n documents'''
    exceptions = ["wikipedia", "youtube", "imdb"]
    n = int(n)
    urls = Urls.query.all()
    urls = [(u.url, u.pod.split('.u.')[0]) for u in urls]
    shuffle(urls)
    for pair in urls[:n]:
        url = pair[0]
        if any(e in url for e in exceptions):
            continue
        pod = pair[1]
        parse = urlparse(url)
        domain = parse.scheme+'://'+parse.netloc
        print(url, pod)
        access, _, _ = request_url(url)
        if access:
            links = extract_links(url)
        for link in links:
            if domain in link:
                print(link+';'+pod+';;'+username)


@pears.cli.command('getlinks')
@click.argument('url')
def get_links(url):
    '''Get links from a particular URL'''
    access, req, request_errors = request_url(url)
    if access:
        links = extract_links(url)
        for link in links:
            print(link)
    else:
        print("Access denied.")


@pears.cli.command('indexwiki')
@click.argument('folder')
@click.argument('regex')
@click.argument('lang')
@click.argument('contributor')
@click.argument('host_url')
def index_wiki(folder, regex, lang, contributor, host_url):
    '''Index Wikipedia corpus in <doc> format,
    as obtained from the WikiNLP scripts.

    Parameters
    - folder: the directory containing your preprocessed documents,
    as obtained from WikiNLP using wikinlp.categories.CatProcessor
    (https://github.com/possible-worlds-research/wikinlp). This should
    be a path ending in 'categories' in your WikiNLP install.
    - regex: a regex filtering which directories from the categories 
    folder should be processed. For example, assuming that categories
    about books have been retrieved, 'Novels_about*' would select the 
    novels about certain topics.
    - lang: the language of the Wikipedia you have processed.
    - contributor: the username of the admin indexing the corpus.
    - host_url: the domain of your instance, e.g. https://mypears.org.

    '''
    corpus_files = glob(join(folder, f'*{regex}*', '*.doc.txt'))
    for filepath in corpus_files:
        print(f">>Processing {filepath}...")
        with open(filepath, encoding='utf-8') as fin:
            url = ""
            title = ""
            doc = ""
            theme = filepath.split('/')[-2]
            theme = theme.replace('_',' ')
            for l in fin:
                l=l.rstrip('\n')
                if l[:4] == "<doc":
                    m = re.search('url=\"([^\"]*)\"',l)
                    url = m.group(1)
                    m = re.search('title=\"([^\"]*)\"',l)
                    title = m.group(1)
                elif "</doc" in l:
                    print(url,theme,title,doc[:30])
                    note = ""
                    if not title.startswith("Talk:"):
                        index_doc_from_cli(title, doc, theme, lang, contributor, url, note, host_url)
                    doc = ""
                else:
                    doc+=l+' '



######################
# CLEAN THINGS UP
######################

@pears.cli.command('deletedbonly')
def deletedbonly():
    urls = Urls.query.all()
    for u in urls:
        db.session.delete(u)
        db.session.commit()
    pods = Pods.query.all()
    for p in pods:
        db.session.delete(p)
        db.session.commit()


#####################
# UNIT TESTS
#####################

@pears.cli.command('unittest')
@click.argument('username')
def checkconsistency(username):
    print("\n>> CLI: UNITTEST: CONSISTENCY CHECKS")
    pods = Pods.query.all()
    usernames = [p.name.split('.u.')[1] for p in pods]
    if username not in usernames:
        print("\t> ERROR: no username",username)
        return 0
    check_idx_to_url(username)
    check_missing_docs_in_npz(username)
    check_duplicates_idx_to_url(username)
    check_db_vs_idx_to_url(username)
    print("\n")
    pods = [p for p in pods if p.name.split('.u.')[1] == username]
    for pod in pods:
        print(">> CLI: UNITTEST: CONSISTENCY: CHECKING POD:", pod.name)
        check_npz_to_idx(pod.name, username, pod.language)
        check_npz_to_idx_vs_idx_to_url(pod.name, username, pod.language)
        check_npz_vs_npz_to_idx(pod.name, username, pod.language)
        check_pos_vs_npz_to_idx(pod.name, username, pod.language)


def check_idx_to_url(username):
    print("\t>> CHECKING IDX_TO_URL")
    pod_path = join(pod_dir, username, username+'.idx')
    idx_to_url = joblib.load(pod_path)
    if len(idx_to_url[0]) != len(idx_to_url[1]):
        print("\t\t> ERROR: the two lists in idx_to_url do not match in length", len(idx_to_url[0]), len(idx_to_url[1]))
    return idx_to_url


def check_db_vs_idx_to_url(username):
    print("\t>> CHECKING DB VS IDX_TO_URL")
    urls = []
    pods = Pods.query.all()
    pods = [p for p in pods if p.name.split('.u.')[1] == username]
    for pod in pods:
        urls.extend(Urls.query.filter_by(pod=pod.name).all())
    urls = [url.url for url in urls]
    pod_path = join(pod_dir, username, username+'.idx')
    idx_to_url = joblib.load(pod_path)
    if len(set(urls)) != len(set(idx_to_url[1])):
        print("\t\t> ERROR: Length of URL set in DB != len(set(idx)) in idx_to_url", len(urls), len(idx_to_url[0]))
        return list(set(urls)-set(idx_to_url[1]))
    return []


def check_duplicates_idx_to_url(username):
    print("\t>> CHECKING DUPLICATES IN IDX_TO_URL")
    pod_path = join(pod_dir, username, username+'.idx')
    idx_to_url = joblib.load(pod_path)
    if len(idx_to_url[0]) > len(list(set(idx_to_url[0]))):
        print("\t\t> ERROR: Duplicates in idx_to_url (idx)")
    if len(idx_to_url[1]) > len(list(set(idx_to_url[1]))):
        print("\t\t> ERROR: Duplicates in idx_to_url (urls)")


def check_missing_docs_in_npz(username):
    print("\t>> CHECKING DOCS IN IDX_TO_URL WITHOUT A VECTOR")
    pod_path = join(pod_dir, username, username+'.idx')
    idx_to_url = joblib.load(pod_path)
    all_npz_idx = []
    pods = Pods.query.all()
    pods = [p for p in pods if p.name.split('.u.')[1] == username]
    for pod in pods:
        pod_path = join(pod_dir, username, pod.language, pod.name+'.npz.idx')
        npz_to_idx = joblib.load(pod_path)
        all_npz_idx.extend(npz_to_idx[1][1:])
    #A URL can be in two pods (home+shared)
    if set(all_npz_idx) != set(idx_to_url[0]):
        diff = list(set(idx_to_url[0])-set(all_npz_idx))
        print("\t\t> ERROR: Some documents in idx_to_url do not have a vector associated with them.")
        print("\t\t>      :", diff)
        return diff
    return []


def check_npz_to_idx(pod, username, language):
    print("\t>> CHECKING NPZ_TO_IDX")
    pod_path = join(pod_dir, username, language, pod+'.npz.idx')
    npz_to_idx = joblib.load(pod_path)
    if len(npz_to_idx[0]) != len(npz_to_idx[1]):
        print("\t\t> ERROR: the two lists in npz_to_idx do not match in length", len(npz_to_idx[0]), len(npz_to_idx[1]))
    if len(npz_to_idx[0]) > len(list(set(npz_to_idx[0]))):
        print("\t\t> ERROR: Duplicates in npz_to_idx (npz)")
    if len(npz_to_idx[1]) > len(list(set(npz_to_idx[1]))):
        print("\t\t> ERROR: Duplicates in npz_to_idx (idx)")


def check_npz_to_idx_vs_idx_to_url(pod, username, language):
    print("\t>> CHECKING NPZ_TO_IDX VS IDX_TO_URL")
    pod_path = join(pod_dir, username, username+'.idx')
    idx_to_url = joblib.load(pod_path)
    pod_path = join(pod_dir, username, language, pod+'.npz.idx')
    npz_to_idx = joblib.load(pod_path)
    idx1 = idx_to_url[0]
    idx2 = npz_to_idx[1][1:] #Ignore first value, which is -1
    if not set(idx2) <= set(idx1):
        print("\t\t> ERROR: idx in npz_to_idx is not a subset of idx in idx_to_url")


def check_npz_vs_npz_to_idx(pod, username, language):
    print("\t>> CHECKING NPZ_TO_IDX VS IDX_TO_URL")
    pod_path = join(pod_dir, username, language, pod+'.npz')
    pod_m = load_npz(pod_path)
    pod_path = join(pod_dir, username, language, pod+'.npz.idx')
    npz_to_idx = joblib.load(pod_path)
    if pod_m.shape[0] != len(npz_to_idx[0]):
        print("\t\t> ERROR: the npz matrix has shape[0]="+str(pod_m.shape[0])+" but npz_to_idx has length "+str(len(npz_to_idx[0])))


def check_pos_vs_npz_to_idx(pod, username, language):
    print("\t>> CHECKING POS VS NPZ_TO_IDX")
    pod_path = join(pod_dir, username, language, pod+'.npz.idx')
    npz_to_idx = joblib.load(pod_path)
    posindex = load_posix(username, language, pod.split(".")[0])
    idx = []
    for token_id in posindex:
        for doc_id, _ in token_id.items():
            idx.append(doc_id)
    idx1 = list(set(idx))
    idx2 = npz_to_idx[1][1:] #Ignore first value, which is -1
    if set(idx2) != set(idx1):
        print("\t\t> ERROR: idx in npz_to_idx do not match doc list in positional index")
        print("\t\t> idx  :", set(idx1))
        print("\t\t> posix:", set(idx2))
    return set(idx1), set(idx2)

#####################
# REBUILD FROM DB
#####################

@pears.cli.command('rebuildfromdb')
@click.argument('basedir')
def rebuild_from_db(basedir):
    from app.cli.rebuild import rebuild_pods_and_urls, rebuild_users, rebuild_personalization
    rebuild_pods_and_urls(pod_dir, basedir)
    rebuild_users(basedir)
    rebuild_personalization(basedir)

@pears.cli.command('updateinstancename')
@click.argument('oldname')
@click.argument('newname')
def update_instance_name(oldname, newname):
    urls = Urls.query.all()
    for u in urls:
        u.share = u.share.replace(oldname, newname)
        db.session.add(u)
        db.session.commit()
