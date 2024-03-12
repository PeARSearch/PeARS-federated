# SPDX-FileCopyrightText: 2022 PeARS Project, <community@pearsproject.org>, 
#
# SPDX-License-Identifier: AGPL-3.0-only

from app.api.models import Urls
from app import db
from os.path import dirname, realpath, join, basename
import numpy as np
from scipy.sparse import vstack, load_npz
from collections import Counter

dir_path = dirname(dirname(realpath(__file__)))
pod_dir = join(dir_path,'static','pods')


def get_url_list_for_users(theme):
    urls = []
    url_theme = theme.replace(' ', '_')
    hfile = join(dir_path, "static", "pods", url_theme + ".pears.txt")
    f_out = open(hfile,'w')
    for url in Urls.query.filter(Urls.pod.contains(theme+'.u.')).all():
        if not url.pod.startswith(theme+'.u.'):
            continue
        urls.append(url.url)
        f_out.write(url.url+'\n')
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
