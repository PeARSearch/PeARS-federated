import logging
logger = logging.getLogger(__name__)
from urllib.parse import urlparse
from os.path import join
import re
import requests
from flask import current_app

def robotcheck(url):
    scheme = urlparse(url).scheme
    domain = scheme + '://' + urlparse(url).netloc
    robot_url = join(domain,"robots.txt")

    disallowed = []
    r = requests.head(robot_url, timeout=30)
    if r.status_code < 400:
        parse = False
        content = requests.get(robot_url).text.splitlines()
        for l in content:
            if 'User-agent: *' in l:
                parse = True
            elif 'User-agent' in l and parse is True:
                parse = False
            elif l == 'Disallow: /' and parse is True:
                disallowed.append(domain)
            elif 'Disallow:' in l and parse is True:
                m = re.search(r'Disallow:\s*(.+)',l)
                if m:
                    u = m.group(1)
                    if u[0] == '/':
                        u = u[1:]
                    disallowed.append(join(domain,u))

    getpage = True
    for u in disallowed:
        m = re.search(u.replace('*','.*'),url)
        if m:
            error = "robotcheck: "+url+" is disallowed because of "+u
            logger.error(error)
            getpage = False
    return getpage

def request_url(url):
    logger.info("Checking URL can be requested")
    access = None
    req = None
    errs = []
    headers = {'User-Agent': current_app.config['USER-AGENT']}
    try:
        req = requests.head(url, timeout=30, headers=headers)
    except:
        error = "request_url: request timed out."
        logger.error(error)
        errs.append(error)
        return access, req, errs
    if req.status_code >= 400:
        error = "request_url: status code is "+str(req.status_code)
        logger.error(error)
        errs.append(error)
        return access, req, errs
    else:
        try:
            if robotcheck(url):
                access = True
            else:
                error = "request_url: robot.txt disallows the url "+url+"."
                logger.error(error)
                errs.append(error)
        except:
            error = "Issues reading the robots.txt file for this site."
            logger.error(error)
            errs.append(error)
    return access, req, errs


