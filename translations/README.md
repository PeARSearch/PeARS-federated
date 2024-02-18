## How to use Flask Babel

* Extract all strings to be translated from the app

```
pybabel extract -F babel.cfg -k lazy_gettext -o messages.pot .
```

* Initialise or update the translation folder for your language. E.g. for German (language code *de*):

```
pybabel init -i messages.pot -d translations -l de
```

or

```
pybabel update -i messages.pot -d translations
```

* Manually change the translations in *app/translations/de/LC_MESSAGES/messages.mo* (or whatever path for your language code).

* Compile with:

```
pybabel compile -d translations
```

