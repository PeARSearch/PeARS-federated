# SPDX-FileCopyrightText: 2023 PeARS Project, <community@pearsproject.org>, 
#
# SPDX-License-Identifier: AGPL-3.0-only

import logging
import subprocess
from shutil import which
from os import getenv, remove
from os.path import join, dirname, realpath
import requests
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from pdfminer.high_level import extract_pages
from pdfminer import pdfparser, pdfdocument
from langdetect import detect
from app import app
from app.indexer import detect_open
from app.api.models import installed_languages
from app.utils import remove_emails

app_dir_path = dirname(dirname(realpath(__file__)))
suggestions_dir_path = getenv("SUGGESTIONS_DIR", join(app_dir_path, 'userdata'))


def pdf_mine(pdf_path, max_pages = 12):
    body = ""
    title = ""
    parse = pdfparser.PDFParser(open(pdf_path,'rb'))
    metadata = pdfdocument.PDFDocument(parse).info
    title = metadata[0]['Title'].decode(encoding='utf-8', errors='ignore').replace('\x00', '')
    #authors = metadata[0]['Author'].decode(encoding='utf-8', errors='ignore').replace('\x00', '')
    if which('pdftotext') is not None:
        subprocess.call(['pdftotext', '-l', str(max_pages), pdf_path])
        txt_path = pdf_path.replace('.pdf','.txt')
        with open(txt_path, 'r') as ftxt:
            body = ftxt.read().replace('\n', ' ')
    else:
        c = 0
        for page_layout in extract_pages(pdf_path):
            for element in page_layout:
                try:
                    body+=element.get_text()
                except:
                    pass
            c+=1
            if c >= max_pages:
                break
    return body, title



def extract_txt(url, contributor):
    '''From history info, extract url, title and body of page,
    cleaned with pdfminer'''
    title = ""
    body_str = ""
    snippet = ""
    cc = False
    language = app.config['LANGS'][0]
    error = None
    snippet_length = app.config['SNIPPET_LENGTH']
    local_pdf_path = join(suggestions_dir_path, contributor+'.'+url.split('/')[-1])
    try:
        req = requests.get(url, allow_redirects=True, timeout=30)
        req.encoding = 'utf-8'
        with open(local_pdf_path,'wb') as f_out:
            f_out.write(req.content)
    except Exception:
        print("ERROR accessing resource", url, "...")
        return title, body_str, language, snippet, cc, error
    
    #try:
    body_str, title = pdf_mine(local_pdf_path)
    body_str = remove_emails(body_str)
    #except Exception:
    #    print("ERROR extracting body text from pdf...")
    #    remove(local_pdf_path)
    #    return title, body_str, language, snippet, cc, error

    if title == "":
        title = url.split('/')[-1]
    try:
        language = detect(body_str)
        print("Language for", url, ":", language)
    except Exception:
        title = ""
        error = "ERROR extract_html: Couldn't detect page language."
        remove(local_pdf_path)
        return title, body_str, language, snippet, cc, error

    if language not in installed_languages:
        error = "ERROR extract_html: language is not supported."
        title = ""
        remove(local_pdf_path)
        return title, body_str, language, snippet, cc, error
    snippet = ' '.join(body_str.split()[:snippet_length])
    #remove(local_pdf_path)
    return title, body_str, language, snippet, cc, error
