# SPDX-FileCopyrightText: 2024 PeARS Project, <community@pearsproject.org>, 
#
# SPDX-License-Identifier: AGPL-3.0-only

from shutil import copy2, copytree
from os.path import dirname, realpath, join
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from random import shuffle
from flask import Blueprint
import click
from app.indexer.controllers import run_indexer_url
from app.indexer.access import request_url
from app.indexer.htmlparser import extract_links
from app.orchard.mk_urls_file import get_reindexable_pod_for_admin
from app.utils_db import create_idx_to_url
from app import db, User, Urls, Pods

pears = Blueprint('pears', __name__)

@pears.cli.command('setadmin')
@click.argument('username')
def set_admin(username):
    '''Use from CLI with flask pears setadmin <username>.'''
    user = User.query.filter_by(username=username).first()
    user.is_admin = True
    db.session.commit()
    print(username,"is now admin.")


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
    Use from CLI with flask pears index <contributor> <path>
    '''
    dir_path = dirname(dirname(dirname(realpath(__file__))))
    pod_dir = join(dir_path,'app','static','pods')
    users = User.query.all()
    for user in users:
        Path(join(pod_dir,user.username)).mkdir(parents=True, exist_ok=True)
        create_idx_to_url(user.username)
    run_indexer_url(filepath, host_url)


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


@pears.cli.command('exporturls')
def export_urls():
    '''Get all URLs on this instance'''
    dir_path = dirname(dirname(dirname(realpath(__file__))))
    user_dir = join(dir_path,'app','static','userdata')
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
    dir_path = dirname(dirname(dirname(realpath(__file__))))
    pod_dir = join(dir_path,'app','static','pods')
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

@pears.cli.command('deletedbonly')
def deletedbonly():
    pods = Pods.query.all()
    for pod in pods:
        urls = Urls.query.filter_by(pod=pod.name).all()
        for u in urls:
            db.session.delete(u)
            db.session.commit()
