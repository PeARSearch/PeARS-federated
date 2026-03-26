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


## Contributing translations

PeARS uses [Flask-Babel](https://python-babel.github.io/flask-babel/) for UI translations. Translation files live in the `translations/` directory.

### Translating into an existing language

1. Open `translations/<lang_code>/LC_MESSAGES/messages.po` in a text editor or a PO editor like [Poedit](https://poedit.net/).
2. Fill in the `msgstr` for each `msgid`. Leave `msgstr` empty to fall back to English.
3. Submit a pull request with your changes. The `.mo` binary files are compiled automatically on merge.

### Adding a new language

1. Extract the current translatable strings:

       pybabel extract -F babel.cfg -k lazy_gettext -o messages.pot .

2. Initialise the new language (replace `fr` with your language code):

       pybabel init -i messages.pot -d translations -l fr

3. Edit `translations/fr/LC_MESSAGES/messages.po` and fill in the translations.
4. Submit a pull request. The `.mo` files are compiled automatically.

The UI language switcher automatically detects new languages when their `.mo` files are present, and displays each language in its native name.

### Updating translations after code changes

When new `gettext()` strings are added to the code, existing translations need to be updated:

    pybabel extract -F babel.cfg -k lazy_gettext -o messages.pot .
    pybabel update -i messages.pot -d translations

This adds new strings to all existing `.po` files while preserving existing translations.

### How it works

- Users can switch the UI language from the language icon in the navigation bar.
- The language preference is stored in the session and also respects the browser's language setting.
- A GitHub Action automatically compiles `.po` → `.mo` when translation changes are pushed to `main`.


##### 5. Set up your configuration

There is a .env template file at *.env-template* in the root directory of the repository. You should copy it to *.env* and fill in the information for your setup.

**Mail configuration:** By default, `MAIL_ENABLED` is set to `false`. In this mode, emails (e.g. signup confirmations, password resets) are logged to `mailing.log` instead of being sent. This is useful for local development and testing. When deploying to production, set `MAIL_ENABLED=true` and configure the `MAIL_SERVER`, `MAIL_PORT`, `EMAIL_USER`, and `EMAIL_PASSWORD` fields with your mail server details.

You should also create an admin user to run your PeARS. You can do so by using the following commands:

```
flask pears create-user <username> <password> <email>
flask pears setadmin <username>
```


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
