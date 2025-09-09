from os.path import basename, join, isdir, isfile, dirname, realpath
from pathlib import Path
import operator
from functools import reduce
import secrets
import string
import re
import time
import os
import random
from glob import glob
from captcha.audio import AudioCaptcha, mix_wave, WAVE_SAMPLE_RATE, BEEP, SILENCE, END_BEEP

app_dir_path = dirname(dirname(dirname(realpath(__file__))))
captcha_dir = os.getenv("CAPTCHA_DIR", join(app_dir_path, '.captchas')) 


class AudioCaptchaWithOptionalNoise(AudioCaptcha):
    """
    Minor modifications to the orignal class to make the background noise optional
    """
    use_noise = False

    def create_wave_body(self, chars: str) -> bytearray:
        voices: t.List[bytearray] = []
        inters: t.List[int] = []
        for c in chars:
            voices.append(self._twist_pick(c))
            i = random.randint(WAVE_SAMPLE_RATE, WAVE_SAMPLE_RATE * 3)
            inters.append(i)

        durations = map(lambda a: len(a), voices)
        length = max(durations) * len(chars) + reduce(operator.add, inters)
        if self.use_noise:
            bg = self.create_background_noise(length, chars)
        else:
            bg = bytearray(length)

        # begin
        pos: int = inters[0]
        for i, v in enumerate(voices):
            end = pos + len(v) + 1
            if self.use_noise:
                bg[pos:end] = mix_wave(v, bg[pos:end])
            else:
                bg[pos:end] = v
            pos = end + inters[i]

        return BEEP + SILENCE + BEEP + SILENCE + BEEP + bg + END_BEEP



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
    # NB: Avoiding 1 and 7, which are too easily confused in captcha
    return "".join([secrets.choice("23456890") for _ in range(5)])


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
