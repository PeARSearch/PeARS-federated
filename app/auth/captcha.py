import uuid
import re
from random import randint
from flask_babel import gettext

def mk_captcha():
    random_str = str(uuid.uuid4().hex)
    random_int = randint(3, 6)
    captcha = gettext("Captcha: write down the last ")+str(random_int)+gettext(" characters of the following string: ")+random_str
    return captcha


def check_captcha(captcha, answer):
    m = re.search(" ([0-9]*) ", captcha)
    i = int(m.group(1))
    m = re.search(": (.*)$", captcha)
    random_str = m.group(1)
    solution = random_str[-i:]
    if answer == solution:
        return True
    else:
        return False
