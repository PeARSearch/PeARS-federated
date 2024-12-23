# SPDX-FileCopyrightText: 2024 PeARS Project, <community@pearsproject.org>, 
#
# SPDX-License-Identifier: AGPL-3.0-only

import os
import re
import json
import requests
from requests.adapters import ConnectionError
import time
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
import pandas as pd
import joblib
from flask import Blueprint, url_for
import click
from werkzeug.security import generate_password_hash
from scipy.sparse import load_npz, csr_matrix, vstack
from selenium import webdriver
from selenium.webdriver.common.by import By
from app.auth import VIEW_FUNCTIONS_PERMISSIONS
from app.auth.decorators import get_func_identifier
from app.indexer.controllers import run_indexer_url, index_doc_from_cli
from app.indexer.access import request_url
from app.indexer.posix import load_posix
from app.indexer.htmlparser import extract_links
from app.orchard.mk_urls_file import get_reindexable_pod_for_admin
from app import app, db, User, Urls, Pods, VEC_SIZE

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
    req = requests.get(model_path, allow_redirects=True)
    bs_obj = BeautifulSoup(req.text, "lxml")
    hrefs = bs_obj.findAll('a', href=True)
    date = "0000-00-00"
    for h in hrefs:
        m = re.search(lang+'wiki.16k.*model',h['href'])
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
    users = User.query.all()
    for user in users:
        Path(join(pod_dir,user.username)).mkdir(parents=True, exist_ok=True)
    run_indexer_url(filepath, host_url)


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
# CLEAN UP CODE
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
# PERMISSION CHECKER
#####################

@pears.cli.command('list_endpoint_permissions')
@click.argument("export_mode")
def list_endpoints(export_mode=None):
    
    assert export_mode in ["csv", "json"]

    endpoint_permissions = {}
    for ep, func in app.view_functions.items():
        func_id = get_func_identifier(func)
        permissions = VIEW_FUNCTIONS_PERMISSIONS.get(func_id)
        if permissions is None:
            # admin + DB management endpoints
            # TODO: find a less hacky way to get the permissions for these
            if ep.split(".")[0] in ["admin", "pods", "urls", "user", "personalization", "suggestions"]:
                permissions = {"login": True, "confirmed": True, "admin": True}
            else:
                # TODO: is this always true??
                permissions = {"login": False, "confirmed": False, "admin": False}
        endpoint_permissions[ep] = permissions

    if export_mode == "csv":
        rows = []
        for ep, permissions in endpoint_permissions.items():
            row_dict = {"endpoint": ep}
            row_dict.update(permissions)
            rows.append(row_dict)
        pd.DataFrame(rows).to_csv("endpoint_permissions.csv")

    elif export_mode == "json":
        with open("endpoint_permissions.json", "w") as f:
            json.dump(endpoint_permissions, f, indent=4)

@pears.cli.command('create_test_users')
def create_test_users():
    with open("testusers.json") as f:
        testusers = json.load(f)

    for tu_profile, tu_data in testusers.items():
        user = User(username=tu_data["username"],
                    password=generate_password_hash(tu_data["password"], method='scrypt'),
                    email=tu_data["email"],
                    is_confirmed=True if tu_profile.startswith("confirmed-") else False,
                    is_admin=True if tu_profile.endswith("-admin") else False,
                    confirmed_on=datetime.now())
        db.session.add(user)
        db.session.commit()
        print(f" test user {tu_data['username']} has been registered.")

@pears.cli.command('test_endpoint_permissions')
@click.argument("manual")
@click.argument("solve_captcha")
def test_endpoint_permissions(manual=False, solve_captcha=False):
    if manual:
        # permissions = pd.read_csv("endpoint_permissions__manual.csv", index_col=0)
        permissions = pd.read_csv("endpoint_permissions__manual.20241221.csv", index_col=0)
    else:
        permissions = pd.read_csv("endpoint_permissions.csv", index_col=0)

    if solve_captcha:
        # secret module! try to reproduce it :) 
        from solve_captcha import test_solve_captcha
    else:
        # get some bogus data to send to the captcha part of the form
        test_solve_captcha = lambda: ("CAPTCHA", "CAPTCHA")

    permissions = permissions.dropna()

    # selenium 
    # (setup for firefox: getting the right gecko driver on ubuntu, see https://stackoverflow.com/a/78110627)
    # uncomment the right version depending on your system
    # geckodriver_path = "/snap/bin/geckodriver" # for recent ubuntus
    geckodriver_path = "/usr/local/bin/geckodriver"  # for other systems
    driver_service = webdriver.FirefoxService(executable_path=geckodriver_path)
    def _start_browser():
        return webdriver.Firefox(service=driver_service)

    # which endpoints have which arugments?
    # (for now, we'll skip the ones that take arguments)
    endpoints_to_arguments = {}
    endpoints_to_methods = {}
    for rule in app.url_map.iter_rules():
        endpoints_to_arguments[rule.endpoint] = rule.arguments
        endpoints_to_methods[rule.endpoint] = rule.methods

    # read test user login info
    with open("testusers.json") as f:
        test_users = json.load(f)
    
    TEST_CASES = [
        {"logged_in": False, "is_confirmed": None, "is_admin": None},
        {"logged_in": True, "is_confirmed": False, "is_admin": False},
        {"logged_in": True, "is_confirmed": True, "is_admin": False},
        {"logged_in": True, "is_confirmed": False, "is_admin": True},
        {"logged_in": True, "is_confirmed": True, "is_admin": True}
    ]

    results = []
    for tc in TEST_CASES:

        print(f"Running test case: {tc}")
        browser = _start_browser()

        user = None
        csrf_token = None
        if tc["logged_in"]:
            if not tc["is_confirmed"] and not tc["is_admin"]:
                user = test_users["unconfirmed-not_admin"]
            elif tc["is_confirmed"] and not tc["is_admin"]:
                user = test_users["confirmed-not_admin"]
            elif not tc["is_confirmed"] and tc["is_admin"]:
                user = test_users["unconfirmed-admin"]
            elif tc["is_confirmed"] and tc["is_admin"]:
                user = test_users["confirmed-admin"]
            csrf_token = _selenium_test_login(browser, user)
        else:
            csrf_token = _selenium_get_csrf_without_login(browser)
        _cookies = browser.get_cookies()
        
        if _cookies:
            cookies = {c["name"]: c["value"] for c in _cookies}
        else:
            cookies = {}
        print(cookies)

        urls = app.url_map.bind("localhost:8080", "/")
        for _, ep_data in permissions.iterrows():
            ep = ep_data["endpoint"]

            endpoint_results = {
                "user": user["username"] if user else None,
                "endpoint": ep,
                "methods": endpoints_to_methods[ep],
                "permissions_login": ep_data["login"],
                "permissions_confirmed": ep_data["confirmed"],
                "permissions_admin": ep_data["admin"],
                "arguments": None,
                "url": None,
                "received_status": None,
                "test_result": 0,  ## 0 = not applicable, -1 = failure, +1 = success 
                "test_result_note": None,
                "test_skipped_reason": None
            }
            results.append(endpoint_results)

            print(ep)
            if ep == "settings.delete_account": # don't do account deletion because the rest of the tests won't work!
                print(f"\t skipping delete account endpoint (TODO: test separately!)")
                endpoint_results["test_skipped_reason"] = "account deletion"

            else:
                url_args = {}
                get_args = {}
                form_args = {} 
                argtype = ep_data["argtype"]
                if argtype == "url":
                    url_args = _parse_endpoint_example_args(ep_data["argex"])
                elif argtype == "get":
                    get_args = _parse_endpoint_example_args(ep_data["argex"])
                elif argtype == "form":
                    form_args = _parse_endpoint_example_args(ep_data["argex"])
                    form_args["csrf_token"] = csrf_token
                url = urls.build(ep, url_args, force_external=True)
                endpoint_results["url"] = url
                print("\t", ep, "->", url)

                # use requests to see if we get the right status code
                # (selenium can't do this out of the box, cf https://github.com/seleniumhq/selenium-google-code-issue-archive/issues/141)
                chosen_method = None
                num_attempts = 5
                for attempt in range(num_attempts):
                    try:
                        methods = endpoints_to_methods[ep]
                        if "GET" in methods:
                            chosen_method = "GET"
                            r = requests.get(url, params=get_args, cookies=cookies)
                        elif "POST" in methods:
                            chosen_method = "POST"
                            if get_args:
                                raise ValueError("Trying to use GET arguments in POST request!")
                            form_args["captcha"], form_args["captcha_answer"] = test_solve_captcha()
                            r = requests.post(url, data=form_args, cookies=cookies)
                        else:
                            raise ValueError("Got endpoint that supports neither GET nor POST, don't know what to do!")
                        break
                    except ConnectionError:
                        print(f"\tAttempt {attempt+1}, can't connect to {url}")
                else: 
                    print(f"\tNo success after {num_attempts} attemps, giving up on {url}")
                    endpoint_results["test_skipped_reason"] = "connection_failure"
                    continue

                should_have_access = _should_have_access(tc, ep_data)
                received_status_code = r.status_code
                endpoint_results["received_status"] = received_status_code

                if received_status_code == 200 and not should_have_access:
                    # check if we've been redirected to the login/confirmation page
                    if r.history and r.history[-1].status_code == 302 and (r.url.startswith("http://localhost:8080/auth/login?next=") or r.url.startswith("http://localhost:8080/auth/inactive")):
                        endpoint_results["test_result"] = 1
                        endpoint_results["test_result_note"] = "redirected to home page as expected"
                    elif ep_data["admin"] and r.url == "http://localhost:8080/":
                        # we have been sent back to the home page, let's check if we get the admin-only message
                        if _selenium_check_admin_warning_displayed(browser, url):
                            endpoint_results["test_result"] = 1
                            endpoint_results["test_result_note"] = "should not have access, is appropriately redirected to home page with admin-only warning"
                        else:
                            endpoint_results["test_result"] = -1
                            endpoint_results["test_result_note"] = "should not have access, is redirected to home page but without message"
                    elif r.history and r.history[-1].status_code == 302 and r.url.startswith("http://localhost:8080/admin/"):
                        # sent back to one of the admin pages?
                        # check for error code
                        if _senelium_check_admin_permission_denied_msg(browser, url):
                            endpoint_results["test_result"] = 1
                            endpoint_results["test_result_note"] = "sent back to admin page with 'permission denied' message, this is appropriate here"
                        else:
                            endpoint_results["test_result"] = 0
                            endpoint_results["test_result_note"] = "sent to admin page without 'permission denied' message, don't know what's going on"

                    else:
                        endpoint_results["test_result"] = -1
                        endpoint_results["test_result_note"] = "appears to have access but should not"
        
                elif received_status_code == 200 and should_have_access:
                    if r.history and r.history[-1].status_code == 302 and (r.url.startswith("http://localhost:8080/auth/login?next=")  or r.url.startswith("http://localhost:8080/auth/inactive")):

                        # exception: some endpoints *should* redirect to /auth/inactive, with a message
                        if ep == "auth.resend_confirmation" and r.url.startswith("http://localhost:8080/auth/inactive") and _selenium_check_confirmation_mail_sent_displayed(browser, url):
                            endpoint_results["test_result"] = 1
                            endpoint_results["test_result_note"] = "should have access, verified flash contents using selenium"
                        else:
                            endpoint_results["test_result"] = -1
                            endpoint_results["test_result_note"] = "should have access but is unexpectedly redirected to login/inactive page"                    
                    
                    # have we been redirected to the home page
                    elif r.history and r.history[-1].status_code == 302 and r.url == "http://localhost:8080/":
                        if chosen_method == "GET" and _selenium_check_admin_warning_displayed(browser, url):
                            endpoint_results["test_result"] = -1
                            endpoint_results["test_result_note"] = "should have access but unexpectedly rerouted to home page with admin warning"
                        else:
                            endpoint_results["test_result"] = 1
                            endpoint_results["test_result_note"] = "rerouted to home page, no warnings found; I'm assuming this means the endpoint was successfully accessed"

                    # sent back to one of the admin pages?
                    elif r.history and r.history[-1].status_code == 302 and r.url.startswith("http://localhost:8080/admin/"):
                        # check for error code
                        if _senelium_check_admin_permission_denied_msg(browser, url):
                            endpoint_results["test_result"] = -1
                            endpoint_results["test_result_note"] = "sent back to admin page with 'permission denied' message, while we should have access"
                        else:
                            endpoint_results["test_result"] = 0
                            endpoint_results["test_result_note"] = "sent to admin page without 'permission denied' message, don't know what's going on"

                    else:
                        endpoint_results["test_result"] = 1
                        endpoint_results["test_result_note"] = "should have access and does"

                elif str(received_status_code).startswith("4") and not should_have_access:
                    endpoint_results["test_result"] = 1
                    endpoint_results["test_result_note"] = "should not have access and gets 4xx response"
                
                elif str(received_status_code).startswith("4") and should_have_access:
                    endpoint_results["test_result"] = -1
                    endpoint_results["test_result_note"] = "should have access but gets 4xx response"

                else:
                    endpoint_results["test_result"] = 0
                    endpoint_results["test_skipped_reason"] = "can't interpret test outcome"

                # browser.get(url)
                # time.sleep(5)

        browser.quit()
        df_results = (
            pd.DataFrame(results)
        )
        df_results_styled = (
            df_results
            .style
            .applymap(
            lambda res: (
                "background-color: green" if res > 0 else 
                "background-color: yellow" if res == 0 else
                "background-color: red"
                ), 
            subset=["test_result"]
            )
        )
        df_results_styled.to_html("permission_tests.html")
        df_results.to_csv("permission_tests.csv")

def _selenium_test_login(browser, user):
    # go to login page 
    browser.get("http://localhost:8080/auth/login")

    # get the CSRF token (needed to test POST requests)
    csrf_token = browser.find_element(By.ID, value="csrf_token").get_attribute("value")

    # fill out and submit the login form
    browser.find_element(By.ID, value="email").send_keys(user["email"])
    browser.find_element(By.ID, value="password").send_keys(user["password"])
    browser.find_element(By.ID, value="submit_button").click()

    return csrf_token

def _selenium_get_csrf_without_login(browser):
    browser.get("http://localhost:8080/auth/login")
    csrf_token = browser.find_element(By.ID, value="csrf_token").get_attribute("value")
    return csrf_token

def _selenium_check_admin_warning_displayed(browser, target_url):
        browser.get(target_url) # redo the request with selenium
        divs = browser.find_elements(By.CLASS_NAME, value="notification.is-danger")
        if divs and "The page you requested is admin only." in divs[0].text:
            return True
        return False

def _senelium_check_admin_permission_denied_msg(browser, target_url):
        browser.get(target_url) # redo the request with selenium
        divs = browser.find_elements(By.CLASS_NAME, value="alert.alert-danger.alert-dismissable")
        if divs and "Permission denied." in divs[0].text:
            return True
        return False


def _selenium_check_confirmation_mail_sent_displayed(browser, target_url):
    browser.get(target_url) # redo the request with selenium
    divs = browser.find_elements(By.CLASS_NAME, value="notification.is-danger")
    
    if divs and "A new confirmation email has been sent." in divs[0].text:
        return True
    return False

def _should_have_access(test_case, endpoint_info):
    if endpoint_info["login"] and not test_case["logged_in"]:
        return False
    if endpoint_info["confirmed"] and not test_case["is_confirmed"]:
        return False
    if endpoint_info["admin"] and not test_case["is_admin"]:
        return False
    return 200

def _parse_endpoint_example_args(arg_string):
    args = {}
    for item in arg_string.split(","):
        item = item.strip()
        m = re.match(r"(?P<key>\S+?):(?P<val>\S+)", item)
        if not m:
            raise ValueError("Argument examples don't follow the correct format!")
        args[m.group("key")] = m.group("val")
    return args


#####################
# REBUILD FROM DB
#####################

@pears.cli.command('rebuildfromdb')
@click.argument('basedir')
def rebuild_from_db(basedir):
    from app.cli.rebuild import rebuild_pods_and_urls, rebuild_users, rebuild_personalization
    #rebuild_pods_and_urls(pod_dir, basedir)
    #rebuild_users(basedir)
    rebuild_personalization(basedir)
