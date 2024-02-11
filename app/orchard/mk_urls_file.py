# SPDX-FileCopyrightText: 2022 PeARS Project, <community@pearsproject.org>, 
#
# SPDX-License-Identifier: AGPL-3.0-only

from app.api.models import Urls, Pods
from app import db
from os.path import dirname, realpath, join, basename
import numpy as np
from scipy.sparse import vstack, load_npz
from collections import Counter

dir_path = dirname(dirname(realpath(__file__)))
pod_dir = join(dir_path,'static','pods')


def make_shareable_pod(keyword):
    urls = []
    url_keyword = keyword.replace(' ', '_')
    hfile = join(dir_path, "static", "pods", url_keyword + ".pears.txt")
    lang = db.session.query(Pods).filter_by(name=keyword).first().language
    f_out = open(hfile,'w')
    for url in db.session.query(Urls).filter_by(pod=keyword).all():
        trigger = ''
        contributor = ''
        if url.trigger is not None:
            trigger = url.trigger
        if url.contributor is not None:
            contributor = url.contributor
            
        urls.append([url.url,trigger,contributor])
        f_out.write(url.url+';'+keyword+';'+lang+';'+trigger+';;'+'\n')
    f_out.close()
    filename = hfile.split('/')[-1]
    return filename, urls


