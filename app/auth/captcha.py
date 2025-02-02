from os.path import basename, join, isdir, isfile, dirname, realpath
from pathlib import Path
import secrets
import string
import re
import time
import os
from glob import glob

app_dir_path = dirname(dirname(dirname(realpath(__file__))))
captcha_dir = os.getenv("CAPTCHA_DIR", join(app_dir_path, '.captchas')) 


def delete_old_captchas():
    cur_time_ns = time.time_ns()
    one_hour_ago = cur_time_ns - 3_600_000_000_000

    for captcha_file in glob(join(captcha_dir, "*.*.txt")):
        base = basename(captcha_file)
        timestamp = int(base.split(".")[0])
        if timestamp < one_hour_ago:
            os.remove(captcha_file)


def generate_captcha_string():
    # String of letters and numbers (will be stored in the server session and be shown 
    # to the user only in the captcha image)
    return "".join([secrets.choice(string.ascii_lowercase) for _ in range(5)])


def mk_captcha():
    """
    Generates a pair of a public ID number and a 'secret' string to be shown in the image 
    """

    print(captcha_dir)
    if not isdir(captcha_dir):
        Path(captcha_dir).mkdir(parents=True, exist_ok=True)
    else:
        # delete all captchas older than an hour
        delete_old_captchas()

    # ID number (will be accessible to the user)
    timestamp_ns = time.time_ns() 
    captcha_id = f"{timestamp_ns}.{secrets.randbelow(10_000)}"
    
    captcha_str = generate_captcha_string()

    with open(join(captcha_dir, f"{captcha_id}.txt"), "w") as f:
        f.write(captcha_str)

    return captcha_id, captcha_str


def check_captcha(captcha_id, captcha_answer):

    captcha_file = join(captcha_dir, f"{captcha_id}.txt")
    if not isfile(captcha_file):
        return False

    with open(captcha_file) as f:
        caption_str = f.read()
    os.remove(captcha_file)
    return caption_str == captcha_answer


def refresh_captcha(captcha_id):

    captcha_file = join(captcha_dir, f"{captcha_id}.txt")
    if not isfile(captcha_file):
        return None

    new_captcha_str = generate_captcha_string()
    with open(captcha_file, "w") as f:
        f.write(new_captcha_str)
    return new_captcha_str
