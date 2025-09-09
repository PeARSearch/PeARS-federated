import requests
from bs4 import BeautifulSoup
import re
from pathlib import Path
from os.path import join
import sys


def install_language(lang):
    local_dir = join(dir_path, "app", "api", "models", lang)
    Path(local_dir).mkdir(exist_ok=True, parents=True)

    # The repository for pretrained models
    model_path = 'https://github.com/possible-worlds-research/pretrained-tokenizers/tree/main/models'

    # this will load the bare page - without the file list
    # we'll just use this to get the cookies so we can spoof the AJAX request that gets the file list
    req_bare_page = requests.get(model_path, allow_redirects=True)

    file_list_url = model_path.replace("/tree/", "/tree-commit-info/")
    req_files = requests.get(
        url=file_list_url,
        cookies=req_bare_page.cookies,
        headers={
            "Accept": "application/json",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "en-US,en;q=0.5",
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Github-Verified-Fetch": "true",
            "Host": "github.com",
            "Pragma": "no-cache",
            "Priority": "u=4",
            "Referer": model_path,
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "Sec-GPC": "1",
            "TE": "trailers",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:141.0) Gecko/20100101 Firefox/141.0"
        }
    )
    model_file_dict = req_files.json()
    date = "0000-00-00"
    for model_file in model_file_dict:
        m = re.search(lang+'wiki.16k.*model', model_file)
        if m:
            date = m.group(0).replace(lang+'wiki.16k.','').replace('.model','')
            break

    repo_path = 'https://github.com/possible-worlds-research/pretrained-tokenizers/blob/main/'
    paths = ['models/'+lang+'wiki.16k.'+date+'.model', 'vocabs/'+lang+'wiki.16k.'+date+'.vocab', 'nns/'+lang+'wiki.16k.'+date+'.cos']

    for p in paths:
        path = join(repo_path, p+'?raw=true')
        filename = p.split('/')[-1].replace(date+'.','')
        local_file = join(local_dir,filename)
        print("Downloading",path,"to",local_file,"...")
        try:
            with open(local_file,'wb') as f:
                f.write(requests.get(path,allow_redirects=True).content)
        except Exception:
            print("Request failed when trying to access", path, "...")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python install-lang.py <language-code>")
        sys.exit(1)

    language_code = sys.argv[1]
    install_language(language_code)
