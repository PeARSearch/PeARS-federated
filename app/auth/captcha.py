import secrets
import string
import re

def mk_captcha():
    """
    Generates a pair of a public ID number and a 'secret' string to be shown in the image 
    """

    # ID number (will be accessible to the user)
    captcha_id = str(secrets.randbelow(10_000))
    
    # String of letters and numbers (will be stored in the server session and be shown 
    # to the user only in the captcha image)
    captcha_str = "".join([secrets.choice(string.ascii_lowercase) for _ in range(5)])

    return captcha_id, captcha_str
