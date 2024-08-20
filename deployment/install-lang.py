import requests
from bs4 import BeautifulSoup
import re
from pathlib import Path
from os.path import join
import sys

def install_language(lang):
    dir_path = Path(__file__).parent.parent
    local_dir = join(dir_path, "app", "api", "models", lang)
    Path(local_dir).mkdir(exist_ok=True, parents=True)
    print(f"Downloading lang to {local_dir}")

    # The repository for pretrained models
    model_path = 'https://github.com/possible-worlds-research/pretrained-tokenizers/tree/main/models'
    req = requests.get(model_path, allow_redirects=True)
    bs_obj = BeautifulSoup(req.text, "lxml")
    hrefs = bs_obj.findAll('a', href=True)
    date = "0000-00-00"
    for h in hrefs:
        m = re.search(lang + 'wiki.16k.*model', h['href'])
        if m:
            date = m.group(0).replace(lang + 'wiki.16k.', '').replace('.model', '')
            break

    repo_path = 'https://github.com/possible-worlds-research/pretrained-tokenizers/blob/main/'
    paths = [
        'models/' + lang + 'wiki.16k.' + date + '.model',
        'vocabs/' + lang + 'wiki.16k.' + date + '.vocab',
        'nns/' + lang + 'wiki.16k.' + date + '.cos'
    ]

    for p in paths:
        path = join(repo_path, p + '?raw=true')
        filename = p.split('/')[-1].replace(date + '.', '')
        local_file = join(local_dir, filename)
        print("Downloading", path, "to", local_file, "...")
        try:
            with open(local_file, 'wb') as f:
                f.write(requests.get(path, allow_redirects=True).content)
        except Exception as e:
            print(f"Request failed when trying to access {path}... Error: {e}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python install-lang.py <language-code>")
        sys.exit(1)

    language_code = sys.argv[1]
    install_language(language_code)