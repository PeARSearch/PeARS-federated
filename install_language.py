# SPDX-FileCopyrightText: 2022 PeARS Project, <community@pearsproject.org> 
#
# SPDX-License-Identifier: AGPL-3.0-only

import sys
import requests
from pathlib import Path
from os.path import dirname, realpath, join

if len(sys.argv) != 2:
    print("Please specify the language you want to install. English is pre-installed. The following other languages are supported: [de,fr]")
    sys.exit()

lang = sys.argv[1]

if len(lang) != 2:
    print("Your language code should just be a two-letter string. \nEXAMPLE USAGE: python install_language.py de.")
    sys.exit()

dir_path = dirname(realpath(__file__))
local_dir = join(dir_path, "app", "api", "models", lang)
Path(local_dir).mkdir(exist_ok=True, parents=True)

repo_path = 'https://github.com/possible-worlds-research/pretrained-tokenizers/blob/main/'

paths = ['models/'+lang+'wiki.16k.2023-11-17.model', 'vocabs/'+lang+'wiki.16k.2023-11-17.vocab', 'nns/'+lang+'wiki.16k.2023-11-17.cos']

for p in paths:
    path = join(repo_path, p+'?raw=true')
    filename = p.split('/')[-1].replace('2023-11-17.','').replace('16k','lite.16k')
    local_file = join(local_dir,filename)
    print("Downloading",path,"to",local_file,"...")
    try:
        with open(local_file,'wb') as f:
            f.write(requests.get(path,allow_redirects=True).content)
    except Exception:
        print("Request failed when trying to index", path, "...")
