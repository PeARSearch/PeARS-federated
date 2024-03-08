# SPDX-FileCopyrightText: 2023 PeARS Project, <community@pearsproject.org>, 
#
# SPDX-License-Identifier: AGPL-3.0-only

import logging
from os.path import join, dirname, realpath
import requests
from urllib.parse import urljoin
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextContainer
from langdetect import detect

from app.indexer import detect_open
from app.api.models import installed_languages
from app import LANGS

dir_path = dirname(dirname(realpath(__file__)))
toindex_dir = join(dir_path,'static','toindex')


def pdf_mine(pdf_path):
    body = ""
    for page_layout in extract_pages(pdf_path):
        for element in page_layout:
            if isinstance(element, LTTextContainer):
                body+=element.get_text()
    return body



def extract_txt(url):
    '''From history info, extract url, title and body of page,
    cleaned with pdfminer'''
    title = ""
    body_str = ""
    snippet = ""
    cc = False
    language = LANGS[0]
    error = None
    try:
        req = requests.get(url, allow_redirects=True, timeout=30)
        req.encoding = 'utf-8'
        with open(join(toindex_dir,'tmp.pdf'),'wb') as f_out:
            f_out.write(req.content)
    except Exception:
        print("ERROR accessing resource", url, "...")
        return title, body_str, language, snippet, cc, error
    
    try:
        body_str = pdf_mine(join(toindex_dir,'tmp.pdf'))
    except Exception:
        print("ERROR extracting body text from pdf...")
        return title, body_str, language, snippet, cc, error

    title = url.split('/')[-1]
    try:
        language = detect(body_str)
        print("Language for", url, ":", language)
    except Exception:
        title = ""
        error = "ERROR extract_html: Couldn't detect page language."
        return title, body_str, language, snippet, cc, error

    if language not in installed_languages:
        error = "ERROR extract_html: language is not supported."
        title = ""
        return title, body_str, language, snippet, cc, error
    snippet = body_str[:90]
    return title, body_str, language, snippet, cc, error
