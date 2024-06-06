# SPDX-FileCopyrightText: 2022 PeARS Project, <community@pearsproject.org>, 
#
# SPDX-License-Identifier: AGPL-3.0-only

import logging
import requests
import justext
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from langdetect import detect
from app.indexer.access import request_url
from app.indexer import detect_open
from app.api.models import installed_languages
from app import app, LANGS, LANGUAGE_CODES

def remove_boilerplates(response, lang):
    text = ""
    print("REMOVING BOILERPLATES FOR LANG",lang,"(",LANGUAGE_CODES[lang],").")
    paragraphs = justext.justext(
        response.content,
        justext.get_stoplist(LANGUAGE_CODES[lang]),
        max_link_density=0.3,
        stopwords_low=0.1,
        stopwords_high=0.3,
        length_low=30,
        length_high=100)
    for paragraph in paragraphs:
        if not paragraph.is_boilerplate:
            text += paragraph.text + " "
    return text


def BS_parse(url):
    bs_obj = None
    req = None
    headers = {'User-Agent': app.config['USER-AGENT']}
    try:
        req = requests.head(url, timeout=30, headers=headers)
    except Exception:
        logging.eror(f"\t>> ERROR: BS_parse: request.head failed trying to access {url}...")
        pass
    if "text/html" not in req.headers["content-type"]:
        logging.error(f"\t>> ERROR: BS_parse: Not a HTML document...")
        return bs_obj, req
    try:
        req = requests.get(url, allow_redirects=True, timeout=30, headers=headers)
        req.encoding = 'utf-8'
    except Exception:
        logging.error(f"\t>> ERROR: BS_parse: request failed trying to access {url}...")
        return bs_obj, req
    bs_obj = BeautifulSoup(req.text, "lxml")
    return bs_obj, req


def extract_links(url):
    links = []
    headers = {'User-Agent': app.config['USER-AGENT']}
    try:
        req = requests.head(url, timeout=30, headers=headers)
        if req.status_code >= 400:
            logging.error(f"\t>> ERROR: extract_links: status code is {req.status_code}")
            return links
        if "text/html" not in req.headers["content-type"]:
            logging.error(f"\t>> ERROR: Not a HTML document...")
            return links
    except Exception:
        logging.error(f"\t>> ERROR: extract_links: request.head failed trying to access {url}...")
        return links
    bs_obj, req = BS_parse(url)
    if not bs_obj:
        return links
    hrefs = bs_obj.findAll('a', href=True)
    for h in hrefs:
        if h['href'].startswith('http') and '#' not in h['href']:
            links.append(h['href'])
        else:
            links.append(urljoin(url, h['href']))
    return links


def extract_html(url):
    '''From history info, extract url, title and body of page,
    cleaned with BeautifulSoup'''
    title = ""
    body_str = ""
    snippet = ""
    cc = False
    language = LANGS[0]
    error = None
    snippet_length = app.config['SNIPPET_LENGTH']
    
    bs_obj, req = BS_parse(url)
    if not bs_obj:
        error = "\t>> ERROR: extract_html: Failed to get BeautifulSoup object."
        return title, body_str, language, snippet, cc, error
    if hasattr(bs_obj.title, 'string'):
        if url.startswith('http'):
            og_title = bs_obj.find("meta", property="og:title")
            og_description = bs_obj.find("meta", property="og:description")
            logging.info(f"OG TITLE: {og_title}")
            logging.info(f"OG DESC: {og_description}")

            # Process title
            if not og_title:
                title = bs_obj.title.string
                if title is None:
                    title = ""
            else:
                title = og_title['content']
            title = ' '.join(title.split()[:snippet_length])
            
            # Get body string
            body_str = remove_boilerplates(req, LANGS[0]) #Problematic...
            logging.debug(body_str[:500])
            try:
                language = detect(title + " " + body_str)
                logging.info(f"\t>> INFO: Language for {url}: {language}")
            except Exception:
                title = ""
                error = "\t>> ERROR: extract_html: Couldn't detect page language."
                return title, body_str, snippet, cc, error
            if language not in installed_languages:
                logging.error(f"\t>> ERROR: extract_html: language {language} is not supported. Moving to default language.")
                language = LANGS[0]
                #title = ""
                #return title, body_str, language, snippet, cc, error
            # Process snippet
            if og_description:
                snippet = og_description['content'][:1000]
            else:
                snippet = ' '.join(body_str.split()[:snippet_length])
    return title, body_str, language, snippet, cc, error
