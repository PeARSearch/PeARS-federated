<!--
SPDX-FileCopyrightText: 2023 PeARS Project, <community@pearsproject.org> 

SPDX-License-Identifier: AGPL-3.0-only
-->

# PeARS Federated


## Important info

*PeARS Federated* is a version of PeARS for federated use. Admins create PeARS instances that users can join to contribute to the index.

*PeARS Federated* is provided as-is. Before you use it, please check the rules of your country on crawling Web content and displaying snippets. And be a good netizen: do not overload people's servers while indexing!


## Installation and Setup

We assume that you will first want to play with your installation locally. The following is meant to help you test PeARS on localhost, on your machine. At the point where you are ready to deploy, please check our wiki for more instructions.

##### 1. Clone this repo on your machine:

```
    git clone https://github.com/PeARSearch/PeARS-federated.git
```

##### 2. **Optional step** Setup a virtualenv in your directory.

If you haven't yet set up virtualenv on your machine, please install it via pip:

    sudo apt-get update

    sudo apt-get install python3-setuptools

    sudo apt-get install python3-pip

    sudo pip install virtualenv

Then change into the PeARS-orchard directory:

    cd PeARS-federated

Then run:

    virtualenv env && source env/bin/activate


##### 3. Install the build dependencies:

From the PeARS-orchard directory, run:

    pip install -r requirements.txt


##### 4. **Optional step** Install further languages


If you want to search and index in several languages at the same time, you can add multilingual support to your English install. To do this:

    python3 install_language.py lc

where you should replace lc with a language code of your choice. For now, we are only supporting English (en) and German (de), but more languages are coming!


##### 5. Run your pear!

While on your local machine, in the root of the repo, run:

    python3 run.py en

(The argument to *run.py* should be the code of your installation's default language. E.g. *en* for English, *de* for German, etc.)

Now, go to your browser at *localhost:8080*. You should see the search page for PeARS. You don't have any pages indexed yet, so go to the F.A.Q. page (link at the top of the page) and follow the short instructions to get you going!

