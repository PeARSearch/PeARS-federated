# SPDX-FileCopyrightText: 2026 PeARS Project, <community@pearsproject.org>, 
#
# SPDX-License-Identifier: AGPL-3.0-only

import re
import logging
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
import justext
from langdetect import detect
from flask import current_app
from app import LANGUAGE_CODES
from app.utils import remove_emails

logger = logging.getLogger(__name__)

def remove_boilerplates(response, lang):
    text = ""
    logger.info("Removing boilerplates for lang %s (%s)", lang, LANGUAGE_CODES[lang])
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
    headers = {'User-Agent': current_app.config['USER-AGENT']}
    try:
        req = requests.head(url, timeout=30, headers=headers)
    except Exception:
        logger.error("BS_parse: request.head failed trying to access %s", url)
        return bs_obj, req
    if "text/html" not in req.headers.get("content-type", ""):
        logger.error("BS_parse: Not a HTML document...")
        return bs_obj, req
    try:
        req = requests.get(url, allow_redirects=True, timeout=30, headers=headers)
        req.encoding = 'utf-8'
    except Exception:
        logger.error("BS_parse: request failed trying to access %s", url)
        return bs_obj, req
    bs_obj = BeautifulSoup(req.text, "lxml")
    return bs_obj, req


def extract_links(url):
    links = []
    headers = {'User-Agent': current_app.config['USER-AGENT']}
    try:
        req = requests.head(url, timeout=30, headers=headers)
        if req.status_code >= 400:
            logger.error("extract_links: status code is %s", req.status_code)
            return links
        if "text/html" not in req.headers["content-type"]:
            logger.error("Not a HTML document...")
            return links
    except Exception:
        logger.error("extract_links: request.head failed trying to access %s", url)
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


def naive_text_extract(bs_obj):
    body_str = ""
    ps = bs_obj.findAll(['h1','h2','h3','h4','p','span'])
    for p in ps:
        text = re.sub(r'{{[^}]*}}','',p.text.strip())
        text = text.strip().replace('\n',' ')
        if text not in ['',':']:
            body_str+=text+' '
    return body_str


def process_page_title(bs_obj, snippet_length):
    '''Check whether page contains open graph info,
    otherwise, get title from beautifulsoup object.
    '''
    og_title = bs_obj.find("meta", property="og:title")
    logger.info("OG title: %s", og_title)
    if not og_title:
        title = bs_obj.title.string
        if title is None:
            title = ""
    else:
        title = og_title['content']
    title = ' '.join(title.split()[:snippet_length])
    return title


def process_body_string(req, bs_obj, title):
    body_str = ""
    og_description = bs_obj.find("meta", property="og:description")
    logger.info("OG desc: %s", og_description)
    tmp_body_str = naive_text_extract(bs_obj)
    try:
        language = detect(title + " " + tmp_body_str)
    except:
        language = current_app.config['LANGS'][0]
    try:
        if language in current_app.config['LANGS']:
            body_str = remove_boilerplates(req, language)
        else:
            if og_description:
                body_str = ' '.join(og_description['content'].split()[:100])+' '
            body_str+=tmp_body_str
    except:
        if og_description:
            body_str = ' '.join(og_description['content'].split()[:100])+' '
        body_str+=tmp_body_str
    body_str = remove_emails(body_str)
    logger.debug("%s", body_str[:500])
    return body_str, og_description


def extract_html(url):
    '''From history info, extract url, title and body of page,
    cleaned with BeautifulSoup'''
    title = ""
    body_str = ""
    snippet = ""
    cc = False #Keep for future reference
    error = None
    language = current_app.config['LANGS'][0]
    snippet_length = current_app.config['SNIPPET_LENGTH']
    bs_obj, req = BS_parse(url)
    if not bs_obj:
        error = "extract_html: Failed to get BeautifulSoup object."
        return title, body_str, language, snippet, cc, error
    if hasattr(bs_obj.title, 'string'):
        if url.startswith('http'):
            title = process_page_title(bs_obj, snippet_length)
            body_str, og_description = process_body_string(req, bs_obj, title)
            try:
                language = detect(title + " " + body_str)
                logger.info("Language for %s: %s", url, language)
            except Exception:
                title = ""
                error = "extract_html: Couldn't detect page language."
                return title, body_str, language, snippet, cc, error
            if language not in current_app.config['LANGS']:
                logger.error("extract_html: language %s is not supported. Moving to default language.", language)
                language = current_app.config['LANGS'][0]
            # Process snippet
            if og_description:
                snippet = og_description['content'][:1000]
            else:
                snippet = ' '.join(body_str.split()[:snippet_length])
    return title, body_str, language, snippet, cc, error
