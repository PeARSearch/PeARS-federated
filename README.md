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

    sudo apt install python3-virtualenv

Then change into the PeARS-orchard directory:

    cd PeARS-federated

Then run:

    virtualenv env && source env/bin/activate


##### 3. Install the build dependencies:

From the PeARS-federated directory, run:

    pip install -r requirements.txt


##### 4. **Optional step** Install further languages


If you want to search and index in several languages at the same time, you can add multilingual support to your English install. To do this:

    flask pears install-language lc

where you should replace lc with a language code of your choice. For now, we are only supporting English (en), German (de), French (fr) and Malayalam (ml) but more languages are coming!


##### 5. Set up your .env

There is a .env template file at *.env-template* in the root directory of the repository. You should copy it to *.env* and fill in the information for your setup.


##### 6. Run your pear!

While on your local machine, in the root of the repo, run:

    python3 run.py


Now, go to your browser at *localhost:8080*. You should see the search page for PeARS. You don't have any pages indexed yet, so go to the F.A.Q. page (link at the top of the page) and follow the short instructions to get you going!


##### 6. Admin only: Be set up for database migrations

From the command line, go to your PeARS directory and run: 

```
flask db init
```

to set up a migration directory.

Then, whenever the models have changed, first generate a migration script:

```
flask db migrate -m "Your message describing the change."
```

And apply the migration script to your database:

```
flask db upgrade
```
