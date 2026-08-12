# SPDX-FileCopyrightText: 2025 PeARS Project, <community@pearsproject.org>
#
# SPDX-License-Identifier: AGPL-3.0-only

from os import getenv, path
from glob import glob
from pathlib import Path
from os.path import join, dirname, realpath
import logging

# Import flask and template operators
from flask import Flask, flash, send_file, send_from_directory, request, abort, render_template, url_for
from flask_migrate import Migrate
from flask_mail import Mail

# Import SQLAlchemy and LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user

USERNAME = getenv('PA_USERNAME') #PythonAnywhere username
DEFAULT_PATH = f'/home/{USERNAME}/PeARS-federated/app/'


####################################
# Define the WSGI application object
####################################

app = Flask(__name__, static_folder='static')

from app.init_logging import run_logging
mail_logger = run_logging()

################
# Configurations
################

from app.init_config import run_config
app = run_config(app)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////home/'+USERNAME+'/PeARS-federated/app.db'

from flask_babel import Babel, gettext
first_lang = app.config['LANGS'][0]
babel = Babel(app)

mail = Mail(app)

# Make sure user data directories exist
Path(path.join(DEFAULT_PATH,'userdata')).mkdir(parents=True, exist_ok=True)


########################
# Load pretrained models
########################
from app.readers import read_vocab, read_cosines
from app.multilinguality import read_language_codes, read_stopwords
from sklearn.feature_extraction.text import CountVectorizer

LANGUAGE_CODES = read_language_codes()
models = dict()
for LANG in app.config['LANGS']:
    models[LANG] = {}
    spm_vocab_path = join(DEFAULT_PATH, f'api/models/{LANG}/{LANG}wiki.16k.vocab')
    ft_path = join(DEFAULT_PATH, f'api/models/{LANG}/{LANG}wiki.16k.cos')
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

########################
# Jinja global variables
########################

dir_path = DEFAULT_PATH
app.config['OWN_BRAND'] = True if getenv('OWN_BRAND', "false").lower() == 'true' else False
logo_path = getenv('LOGO_PATH', '')
if logo_path != '' and path.isfile(join(logo_path, "logo.png")):
    app.config['LOGO_PATH'] = logo_path
else:
    app.config['LOGO_PATH'] = join(dir_path,'static','assets')

@app.context_processor
def inject_brand():
    """Inject brand information into page
    (logo on all pages and info on start page.)
    """
    return dict(own_brand=app.config['OWN_BRAND'], logo_path=app.config['LOGO_PATH'])

@app.route('/static/assets/<path:path>')
def serve_logos(path):
    return send_from_directory(app.config['LOGO_PATH'], path)



##########
# Database
##########
db = SQLAlchemy(app)
migrate = Migrate(app, db)


#########
# Modules
#########

# Import a module / component using its blueprint handler variable (mod_auth)
from app.indexer.controllers import indexer as indexer_module
from app.api.controllers import api as api_module
from app.search.controllers import search as search_module
#from app.analysis.controllers import analysis as analysis_module
from app.orchard.controllers import orchard as orchard_module
from app.pages.controllers import pages as pages_module
from app.settings.controllers import settings as settings_module
from app.auth.controllers import auth as auth_module

# Register blueprint(s)
app.register_blueprint(indexer_module)
app.register_blueprint(api_module)
app.register_blueprint(search_module)
#app.register_blueprint(analysis_module)
app.register_blueprint(orchard_module)
app.register_blueprint(pages_module)
app.register_blueprint(settings_module)
app.register_blueprint(auth_module)
# ..

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

if not app.config['LIVE_MATRIX']:
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

from app.search.cross_instance_search import filter_instances_by_language
from flask import url_for
import threading
import numpy as np

# Initialize with empty values so the app can serve requests immediately.
# A background thread will populate these once the remote instances respond.
instances = []
M = np.array([])

def _load_remote_instances():
    global instances, M
    try:
        instances, M, skipped = filter_instances_by_language()
        if skipped:
            for s in skipped:
                logging.warning(f"Skipped remote instance {s['instance']}: {s['reason']}")
        logging.info(f"Loaded {len(instances)} remote instance(s) in background.")
    except Exception as e:
        logging.error(f"Failed to load remote instances: {e}")

_instance_loader = threading.Thread(target=_load_remote_instances, daemon=True)
_instance_loader.start()

_sitename_check_completed = False
@app.before_request
def check_sitename_and_hostname():
    global _sitename_check_completed
    if not _sitename_check_completed: # only do this once
        host_url = url_for("search.index", _external=True)
        if host_url.rstrip("/") != app.config["SITENAME"]:
            logging.error("`host_url` and `SITENAME` do not match -- this can cause errors, correct this unless you know what you are doing!")
        _sitename_check_completed = True

#######
# Admin
#######

# Authentification
class MyLoginManager(LoginManager):
    def unauthorized(self):
        return abort(404)

login_manager = MyLoginManager()
login_manager.login_view = 'auth.login'
login_manager.init_app(app)

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
