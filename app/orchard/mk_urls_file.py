# SPDX-FileCopyrightText: 2022 PeARS Project, <community@pearsproject.org>, 
#
# SPDX-License-Identifier: AGPL-3.0-only

from app.api.models import Urls
from app import db, LANG
from os.path import dirname, realpath, join, basename
import numpy as np
from scipy.sparse import vstack, load_npz
from collections import Counter

dir_path = dirname(dirname(realpath(__file__)))
pod_dir = join(dir_path,'static','pods')


def make_shareable_pod(theme):
    urls = []
    url_theme = theme.replace(' ', '_')
    hfile = join(dir_path, "static", "pods", url_theme + ".pears.txt")
    f_out = open(hfile,'w')
    for url in Urls.query.filter(Urls.pod.contains(theme)).all():
        trigger = ''
        if url.trigger is not None:
            trigger = url.trigger
            
        urls.append([url.url,trigger])
        f_out.write(url.url+';'+theme+';'+LANG+';'+trigger+';;'+'\n')
    f_out.close()
    filename = hfile.split('/')[-1]
    return filename, urls


