# SPDX-FileCopyrightText: 2022 PeARS Project, <community@pearsproject.org>, 
#
# SPDX-License-Identifier: AGPL-3.0-only

from os.path import dirname, realpath, join
from os import getenv
from flask import request
from app.api.models import Urls
from app import app

dir_path = dirname(dirname(realpath(__file__)))
pod_dir = getenv("PODS_DIR", join(dir_path, 'pods'))


def get_url_list_for_users(theme):
    urls = []
    url_theme = theme.replace(' ', '_')
    hfile = join(pod_dir, url_theme + ".pears.txt")
    f_out = open(hfile,'w', encoding='utf-8')
    for entry in Urls.query.filter(Urls.pod.contains(theme+'.u.')).all():
        if not entry.pod.startswith(theme+'.u.'):
            continue
        if entry.url.startswith('pearslocal'):
            display_url = join(request.host_url,'api','get?url='+entry.url)
            snippet = entry.snippet
        else:
            display_url = entry.url
            snippet = ' '.join(entry.snippet.split()[:app.config['SNIPPET_LENGTH']])
        urls.append({
            'url': display_url,
            'title': entry.title or '',
            'snippet': snippet or '',
        })
        f_out.write(display_url+'\n')
    f_out.close()
    filename = hfile.split('/')[-1]
    return filename, urls


def get_reindexable_pod_for_admin(theme):
    urls = []
    for url in Urls.query.filter(Urls.pod.contains(theme+'.u.')).all():
        if not url.pod.startswith(theme+'.u.'):
            continue
        user = url.contributor
        user = user.replace('@','') #legacy fix
        note = ''
        if url.notes is not None:
            note = '"'+url.notes+'"'
        urls.append(url.url+';'+theme+';'+note+';'+user)
    return urls
