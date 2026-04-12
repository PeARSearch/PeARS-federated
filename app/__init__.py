# SPDX-FileCopyrightText: 2025 PeARS Project, <community@pearsproject.org> 
#
# SPDX-License-Identifier: AGPL-3.0-only

from os import getenv, path
from glob import glob
from pathlib import Path
from os.path import join, dirname, realpath, isfile
import logging
logger = logging.getLogger(__name__)

# Import flask and template operators
from flask import Flask, flash, render_template, send_file, send_from_directory, request, abort, url_for
from flask_login import current_user

# Extensions are created in app.extensions to avoid circular imports.
from app.extensions import db, migrate, mail, login_manager

dir_path = dirname(realpath(__file__))


####################################
# Define the WSGI application object
####################################

app = Flask(__name__, static_folder='static')

from app.init_logging import run_logging
mail_logger = run_logging()


################
# Configurations
################

from flask_babel import Babel, gettext, refresh as babel_refresh
from flask import session

# Support testing: when _PEARS_CONFIG is set, use that config class
# instead of the normal init_config path.
_config_override = getenv('_PEARS_CONFIG')
if _config_override == 'testing':
    from config import TestingConfig
    app.config.from_object(TestingConfig)
    app.config.setdefault('USER-AGENT', 'PeARSbot-test/0.1')
else:
    from app.init_config import run_config
    app = run_config(app)

first_lang = app.config['LANGS'][0]


def get_available_ui_languages():
    """Return dict of locale code -> native display name for available UI translations."""
    import os
    from babel import Locale
    default_locale = app.config['BABEL_DEFAULT_LOCALE']
    trans_dir = app.config.get('BABEL_TRANSLATION_DIRECTORIES')
    available = {}
    # Default locale is always available (needs no translation files)
    available[default_locale] = Locale.parse(default_locale).get_display_name()
    # Scan translations directory for compiled .mo files
    if trans_dir and os.path.isdir(trans_dir):
        for entry in os.listdir(trans_dir):
            mo_path = os.path.join(trans_dir, entry, 'LC_MESSAGES', 'messages.mo')
            if os.path.isfile(mo_path):
                try:
                    available[entry] = Locale.parse(entry).get_display_name()
                except Exception:
                    continue
    return available

AVAILABLE_UI_LANGUAGES = get_available_ui_languages()


def get_locale():
    # 1. Explicit user choice stored in session
    locale = session.get('locale')
    if locale and locale in AVAILABLE_UI_LANGUAGES:
        return locale
    # 2. Best match from browser Accept-Language header
    best = request.accept_languages.best_match(AVAILABLE_UI_LANGUAGES.keys())
    if best:
        return best
    # 3. Fall back to configured default
    return app.config['BABEL_DEFAULT_LOCALE']

babel = Babel(app, locale_selector=get_locale)

# Make sure user data directories exist
DEFAULT_PATH = dir_path
Path(path.join(DEFAULT_PATH,'userdata')).mkdir(parents=True, exist_ok=True)
if getenv("SUGGESTIONS_DIR", "") != "":
    Path(getenv("SUGGESTIONS_DIR")).mkdir(parents=True, exist_ok=True)

# Initialize extensions with the app
db.init_app(app)
migrate.init_app(app, db)
mail.init_app(app)
login_manager.init_app(app)


########################
# Jinja global variables
########################

app.config['OWN_BRAND'] = True if getenv('OWN_BRAND', "false").lower() == 'true' else False
logo_path = getenv('LOGO_PATH', '')
if logo_path != '' and isfile(join(logo_path, "logo.png")):
    app.config['LOGO_PATH'] = logo_path
else:
    app.config['LOGO_PATH'] = join(dir_path,'static','assets')

@app.context_processor
def inject_brand():
    """Inject brand information into page
    (logo on all pages and info on start page.)
    """
    return dict(own_brand=app.config['OWN_BRAND'], logo_path=app.config['LOGO_PATH'])

@app.context_processor
def inject_locale():
    """Inject available UI languages and current locale into all templates."""
    from flask_babel import get_locale as babel_get_locale
    return dict(
        available_languages=AVAILABLE_UI_LANGUAGES,
        current_locale=str(babel_get_locale()),
    )

@app.route('/static/assets/<path:path>')
def serve_logos(path):
    return send_from_directory(app.config['LOGO_PATH'], path)


########################
# Load pretrained models
########################

LANGUAGE_CODES = {}
models = dict()
VEC_SIZE = 0

if app.config.get('LOAD_MODELS', True):
    from app.readers import read_vocab, read_cosines
    from app.multilinguality import read_language_codes, read_stopwords
    from sklearn.feature_extraction.text import CountVectorizer

    LANGUAGE_CODES = read_language_codes()
    for LANG in app.config['LANGS']:
        models[LANG] = {}
        spm_vocab_path = f'app/api/models/{LANG}/{LANG}wiki.16k.vocab'
        ft_path = f'app/api/models/{LANG}/{LANG}wiki.16k.cos'
        vocab, inverted_vocab, logprobs = read_vocab(spm_vocab_path)
        vectorizer = CountVectorizer(vocabulary=vocab, lowercase=True, token_pattern='[^ ]+')
        ftcos = read_cosines(ft_path)
        models[LANG]['vocab'] = vocab
        models[LANG]['inverted_vocab'] = inverted_vocab
        models[LANG]['logprobs'] = logprobs
        models[LANG]['vectorizer'] = vectorizer
        models[LANG]['nns'] = ftcos
        if LANG in LANGUAGE_CODES:
            models[LANG]['stopwords'] = read_stopwords(LANGUAGE_CODES[LANG].lower())
        else:
            models[LANG]['stopwords'] = []

    # All vocabs have the same vector size
    VEC_SIZE = len(models[first_lang]['vocab'])

##########
# Database
##########




#########
# Modules
#########

# Import a module / component using its blueprint handler variable (mod_auth)
from app.indexer.controllers import indexer as indexer_module
from app.api.controllers import api as api_module
from app.search.controllers import search as search_module
from app.orchard.controllers import orchard as orchard_module
from app.pages.controllers import pages as pages_module
from app.settings.controllers import settings as settings_module
from app.auth.controllers import auth as auth_module

# Register blueprint(s)
app.register_blueprint(indexer_module)
app.register_blueprint(api_module)
app.register_blueprint(search_module)
app.register_blueprint(orchard_module)
app.register_blueprint(pages_module)
app.register_blueprint(settings_module)
app.register_blueprint(auth_module)


# Build the database:
# This will create the database file using SQLAlchemy
# db.drop_all()
with app.app_context():
    db.create_all()

@app.before_request
def check_under_maintenance():
    if reroute_for_maintenance(request.path):
        abort(503)

from app.settings.controllers import get_maintance_mode
def reroute_for_maintenance(path):
    if not get_maintance_mode():
        return False
    if path in [url_for('settings.toggle_maintenance_mode'), url_for('auth.login'), url_for('auth.logout')]:
        return False
    if '/static/' in path:
        return False
    return True


##############
# Optimization
##############

dir_path = dirname(realpath(__file__))
pod_dir = getenv("PODS_DIR", join(dir_path, 'pods'))

if app.config.get('LOAD_MODELS', True) and not app.config.get('LIVE_MATRIX', False):
    from app.search.score_pages import mk_vec_matrix
    for LANG in app.config['LANGS']:
        npzs = glob(join(pod_dir,'*',LANG,'*.u.*npz'))
        if len(npzs) == 0:
            continue
        m, bins, podnames, urls = mk_vec_matrix(LANG)
        models[LANG]['m'] = m
        models[LANG]['mbins'] = bins
        models[LANG]['podnames'] = podnames
        models[LANG]['urls'] = urls


#######################
# Decentralized search
#######################

import threading
import numpy as np

# Initialize with empty values so the app can serve requests immediately.
# A background thread will populate these once the remote instances respond.
instances = []
M = np.array([])

if not app.config.get('TESTING'):
    from app.search.cross_instance_search import filter_instances_by_language

    def _load_remote_instances():
        global instances, M
        with app.app_context():
            try:
                instances, M, skipped = filter_instances_by_language()
                if skipped:
                    for s in skipped:
                        logger.warning("Skipped remote instance %s: %s", s['instance'], s['reason'])
                logger.info("Loaded %d remote instance(s) in background.", len(instances))
            except Exception as e:
                logger.error("Failed to load remote instances: %s", e)

    _instance_loader = threading.Thread(target=_load_remote_instances, daemon=True)
    _instance_loader.start()

    _sitename_check_completed = False
    @app.before_request
    def check_sitename_and_hostname():
        global _sitename_check_completed
        if not _sitename_check_completed: # only do this once
            host_url = url_for("search.index", _external=True)
            if host_url.rstrip("/") != app.config["SITENAME"]:
                logger.error("`host_url` and `SITENAME` do not match -- this can cause errors, correct this unless you know what you are doing!")
            _sitename_check_completed = True


#######
# Admin
#######

from app.api.models import User

@login_manager.user_loader
def load_user(user_id):
    # since the user_id is just the primary key of our user table, use it in the query for the user
    return User.query.get(int(user_id))

from app.admin_views import admin_views_bp
from app.admin_views.registrations import register_all

register_all()
app.register_blueprint(admin_views_bp)


@app.errorhandler(404)
def page_not_found(e):
    flash("The page that you are trying to access doesn't exist or you don't have sufficient permissions to access it. If you're not logged in, log in and try accessing the page again. If you're sure the page exists and that you should have access to it, contact the administrators.", "warning")
    return render_template("404.html"), 404

@app.errorhandler(503)
def maintenance_mode(e):
    flash("We are doing some (hopefully) quick maintenance on this instance. Please check back later!", "warning")
    return render_template("503.html"), 503

@app.route('/manifest.json')
def serve_manifest():
    return send_file('manifest.json', mimetype='application/manifest+json')

@app.route('/sw.js')
def serve_sw():
    return send_file('sw.js', mimetype='application/javascript')

@app.route('/robots.txt')
def static_from_root():
 return send_from_directory(app.static_folder, request.path[1:])


from app.cli.controllers import pears as pears_module
app.register_blueprint(pears_module)
