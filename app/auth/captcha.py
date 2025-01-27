import secrets
import string
import re
import time
import os
import glob


def delete_old_captchas():
    cur_time_ns = time.time_ns()
    one_hour_ago = cur_time_ns - 3_600_000_000_000

    for captcha_file in glob.glob(".captchas/*.*.txt"):
        basename = os.path.basename(captcha_file)
        timestamp = int(basename.split(".")[0])
        if timestamp < one_hour_ago:
            os.remove(captcha_file)

def mk_captcha():
    """
    Generates a pair of a public ID number and a 'secret' string to be shown in the image 
    """

    if not os.path.isdir(".captchas"):
        os.mkdir(".captchas")
    else:
        # delete all captchas older than an hour
        delete_old_captchas()

    # ID number (will be accessible to the user)
    timestamp_ns = time.time_ns() 
    captcha_id = f"{timestamp_ns}.{secrets.randbelow(10_000)}"
    
    # String of letters and numbers (will be stored in the server session and be shown 
    # to the user only in the captcha image)
    captcha_str = "".join([secrets.choice(string.ascii_lowercase) for _ in range(5)])

    with open(f".captchas/{captcha_id}.txt", "w") as f:
        f.write(captcha_str)

    return captcha_id, captcha_str


def check_captcha(captcha_id, captcha_answer):

    captcha_file = f".captchas/{captcha_id}.txt"
    if not os.path.isfile(captcha_file):
        return False

    with open(captcha_file) as f:
        caption_str = f.read()
    os.remove(captcha_file)
    return caption_str == captcha_answer
