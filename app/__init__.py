# SPDX-FileCopyrightText: 2024 PeARS Project, <community@pearsproject.org> 
#
# SPDX-License-Identifier: AGPL-3.0-only

import logging
from os import getenv, path
from glob import glob
from pathlib import Path
from os.path import join, dirname, realpath

# Import flask and template operators
from flask import Flask, flash, render_template, send_file, send_from_directory, request
from flask_admin import Admin, AdminIndexView
from flask_mail import Mail

# Import SQLAlchemy and LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, current_user

#########
# Logging
#########

# Set up basic logging configuration for the root logger
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
logging.basicConfig(level=logging.ERROR, filename="system.log", format='%(asctime)s | %(levelname)s : %(message)s')
logging.getLogger('werkzeug').setLevel(logging.ERROR)
logging.error("Checking system logs on init.")

# Define a custom log level
MAILING = 55
logging.MAILING = MAILING
logging.addLevelName(logging.MAILING, 'MAILING')

# Define a custom logging method for the new level
def mailing(self, message, *args, **kwargs):
    if self.isEnabledFor(logging.MAILING):
        self._log(logging.MAILING, message, args, **kwargs)

# Add the custom logging method to the logger class
logging.Logger.mailing = mailing

# Set up logger
def setup_logger(name, log_file, level=logging.INFO):
    """To setup as many loggers as you want"""

    handler = logging.FileHandler(log_file)        
    handler.setFormatter(formatter)

    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(handler)

    return logger

mail_logger = setup_logger('mailing_logger', 'mailing.log', level=logging.MAILING)
mail_logger.mailing("Checking mailing logs on init.")

####################################
# Define the WSGI application object
####################################

app = Flask(__name__, static_folder='static')

################
# Configurations
################
from dotenv import load_dotenv
app.config.from_object('config')

load_dotenv()
LANGS = getenv('PEARS_LANGS', "en").split(',')
OWN_BRAND = True if getenv('OWN_BRAND', "false").lower() == 'true' else False
app.config['MAIL_DEFAULT_SENDER'] = getenv("MAIL_DEFAULT_SENDER")
app.config['MAIL_SERVER'] = getenv("MAIL_SERVER")
app.config['MAIL_PORT'] = getenv("MAIL_PORT")
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_DEBUG'] = False
app.config['MAIL_USERNAME'] = getenv("EMAIL_USER")
app.config['MAIL_PASSWORD'] = getenv("EMAIL_PASSWORD")
app.config['SITENAME'] = getenv("SITENAME")
app.config['SITE_TOPIC'] = getenv("SITE_TOPIC")
app.config['SEARCH_PLACEHOLDER'] = getenv("SEARCH_PLACEHOLDER")
app.config['SQLALCHEMY_DATABASE_URI'] = getenv("SQLALCHEMY_DATABASE_URI", app.config.get("SQLALCHEMY_DATABASE_URI"))
app.config['USER-AGENT'] = "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; PeARSbot/0.1; +https://www.pearsproject.org/) Chrome/W.X.Y.Z Safari/537.36"

# Legal
app.config['ORG_NAME'] = getenv("ORG_NAME")
app.config['ORG_ADDRESS'] = getenv("ORG_ADDRESS")
app.config['ORG_EMAIL'] = getenv("ORG_EMAIL")
app.config['APPLICABLE_LAW'] = getenv("APPLICABLE_LAW")
app.config['SERVERS'] = getenv("SERVERS")
app.config['EU_SPECIFIC'] = True if getenv("EU_SPECIFIC", "false").lower() == 'true' else False
app.config['SNIPPET_LENGTH'] = int(getenv("SNIPPET_LENGTH"))

# User-related settings
app.config['NEW_USERS'] = True if getenv("NEW_USERS_ALLOWED", "false").lower() == 'true' else False

# Localization
from flask_babel import Babel, gettext
app.config['BABEL_DEFAULT_LOCALE'] = LANGS[0]
app.config['BABEL_TRANSLATION_DIRECTORIES'] = getenv("TRANSLATION_DIR")
babel = Babel(app)

# Optimization
app.config['MAX_PODS'] = int(getenv("MAX_PODS"))
app.config['LIVE_MATRIX'] = True if getenv("LIVE_MATRIX", "false").lower() == 'true' else False
app.config['LOADED_POS_INDEX'] = int(getenv("LOADED_POS_INDEX"))

# Make sure user data directories exist
DEFAULT_PATH = f'app'
Path(path.join(DEFAULT_PATH,'userdata')).mkdir(parents=True, exist_ok=True)
Path(path.join(DEFAULT_PATH,'admindata')).mkdir(parents=True, exist_ok=True)
if getenv("SUGGESTIONS_DIR", "") != "":
    Path(getenv("SUGGESTIONS_DIR")).mkdir(parents=True, exist_ok=True)

# Mail
mail = Mail(app)

########################
# Load pretrained models
########################

from app.readers import read_vocab, read_cosines
from app.multilinguality import read_language_codes, read_stopwords
from sklearn.feature_extraction.text import CountVectorizer

LANGUAGE_CODES = read_language_codes()
models = dict()
for LANG in LANGS:
    models[LANG] = {}
    spm_vocab_path = f'app/api/models/{LANG}/{LANG}wiki.lite.16k.vocab'
    ft_path = f'app/api/models/{LANG}/{LANG}wiki.lite.16k.cos'
    vocab, inverted_vocab, logprobs = read_vocab(spm_vocab_path)
    vectorizer = CountVectorizer(vocabulary=vocab, lowercase=True, token_pattern='[^ ]+')
    ftcos = read_cosines(ft_path)
    models[LANG]['vocab'] = vocab
    models[LANG]['inverted_vocab'] = inverted_vocab
    models[LANG]['logprobs'] = logprobs
    models[LANG]['vectorizer'] = vectorizer
    models[LANG]['nns'] = ftcos
    models[LANG]['stopwords'] = read_stopwords(LANGUAGE_CODES[LANG].lower())

# All vocabs have the same vector size
VEC_SIZE = len(models[LANGS[0]]['vocab'])

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


# Build the database:
# This will create the database file using SQLAlchemy
# db.drop_all()
with app.app_context():
    db.create_all()


##############
# Optimization
##############

dir_path = dirname(realpath(__file__))
pod_dir = getenv("PODS_DIR", join(dir_path, 'pods'))

if not app.config['LIVE_MATRIX']:
    from app.search.score_pages import mk_vec_matrix
    for LANG in LANGS:
        npzs = glob(join(pod_dir,'*',LANG,'*.u.*npz'))
        if len(npzs) == 0:
            continue
        m, bins, podnames = mk_vec_matrix(LANG)
        models[LANG]['m'] = m
        models[LANG]['mbins'] = bins
        models[LANG]['podnames'] = podnames

if app.config['LOADED_POS_INDEX'] > 0:
    from app.indexer.posix import load_posindices
    for LANG in LANGS:
        models[LANG]['posix'] = load_posindices(LANG, n=app.config['LOADED_POS_INDEX'])


#######
# Admin
#######

from flask_admin.contrib.sqla import ModelView
from app.api.models import Pods, Urls, User
from app.api.controllers import return_pod_delete
from app.utils_db import delete_url_representations

from flask_admin import expose
from flask_admin.contrib.sqla.view import ModelView
from flask_admin.model.template import EndpointLinkRowAction

# Authentification
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.init_app(app)

from app.api.models import User

@login_manager.user_loader
def load_user(user_id):
    # since the user_id is just the primary key of our user table, use it in the query for the user
    return User.query.get(int(user_id))



# Flask and Flask-SQLAlchemy initialization here

class MyAdminIndexView(AdminIndexView):
    def is_accessible(self):
        return current_user.is_admin # This does the trick rendering the view only if the user is admin


admin = Admin(app, name='PeARS DB', template_mode='bootstrap3', index_view=MyAdminIndexView())


class UrlsModelView(ModelView):
    list_template = 'admin/pears_list.html'
    column_exclude_list = ['vector','snippet','date_created','date_modified']
    column_searchable_list = ['url', 'title', 'doctype', 'notes', 'pod']
    column_editable_list = ['notes']
    can_edit = True
    page_size = 100
    form_widget_args = {
        'vector': {
            'readonly': True
        },
        'url': {
            'readonly': True
        },
        'pod': {
            'readonly': True
        },
        'snippet': {
            'readonly': True
        },
        'date_created': {
            'readonly': True
        },
        'date_modified': {
            'readonly': True
        },
    }
    def delete_model(self, model):
        try:
            self.on_model_delete(model)
            print("DELETING",model.url)
            # Add your custom logic here and don't forget to commit any changes e.g.
            print(delete_url_representations(model.url))
            self.session.commit()
        except Exception as ex:
            if not self.handle_view_exception(ex):
                flash(gettext('Failed to delete record. %(error)s', error=str(ex)), 'error')

            self.session.rollback()

            return False
        else:
            self.after_model_delete(model)

        return True

class PodsModelView(ModelView):
    list_template = 'admin/pears_list.html'
    column_exclude_list = ['DS_vector','word_vector']
    column_searchable_list = ['url', 'name', 'description', 'language']
    can_edit = False
    page_size = 50
    form_widget_args = {
        'DS_vector': {
            'readonly': True
        },
        'word_vector': {
            'readonly': True
        },
        'date_created': {
            'readonly': True
        },
        'date_modified': {
            'readonly': True
        },
    }
    def delete_model(self, model):
        try:
            self.on_model_delete(model)
            print("DELETING",model.name)
            # Add your custom logic here and don't forget to commit any changes e.g.
            print(return_pod_delete(model.name))
            self.session.commit()
        except Exception as ex:
            if not self.handle_view_exception(ex):
                flash(gettext('Failed to delete record. %(error)s', error=str(ex)), 'error')

            self.session.rollback()

            return False
        else:
            self.after_model_delete(model)

        return True

class UsersModelView(ModelView):
    list_template = 'admin/pears_list.html'
    column_exclude_list = ['password']
    column_searchable_list = ['email', 'username']
    can_edit = True
    page_size = 50
    form_widget_args = {
        'email': {
            'readonly': True
        },
        'password': {
            'readonly': True
        },
        'username': {
            'readonly': True
        },
        'is_confirmed': {
            'readonly': True
        },
        'confirmed_on': {
            'readonly': True
        },
    }


admin.add_view(PodsModelView(Pods, db.session))
admin.add_view(UrlsModelView(Urls, db.session))
admin.add_view(UsersModelView(User, db.session))

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
