# SPDX-FileCopyrightText: 2023 PeARS Project, <community@pearsproject.org> 
#
# SPDX-License-Identifier: AGPL-3.0-only

import os
import click
import logging
from pathlib import Path

# Import flask and template operators
from flask import Flask, render_template, send_file, send_from_directory, request
from flask_admin import Admin, AdminIndexView
from flask_mail import Mail

# Import SQLAlchemy and LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user

# Global variables
EXPERT_ADD_ON = False
OWN_BRAND = False
WALKTHROUGH = False

# Logging
def configure_logging():
    # register root logging
    logging.basicConfig(level=logging.ERROR)
    logging.getLogger('werkzeug').setLevel(logging.ERROR)

configure_logging()

# Define the WSGI application object
app = Flask(__name__, static_folder='static')

# Configurations
from dotenv import load_dotenv
app.config.from_object('config')

load_dotenv()
app.config['MAIL_DEFAULT_SENDER'] = os.getenv("MAIL_DEFAULT_SENDER")
app.config['MAIL_SERVER'] = os.getenv("MAIL_SERVER")
app.config['MAIL_PORT'] = os.getenv("MAIL_PORT")
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_DEBUG'] = False
app.config['MAIL_USERNAME'] = os.getenv("EMAIL_USER")
app.config['MAIL_PASSWORD'] = os.getenv("EMAIL_PASSWORD")


# Make sure user data directories exist
DEFAULT_PATH = f'app'
Path(os.path.join(DEFAULT_PATH,'static/userdata')).mkdir(parents=True, exist_ok=True)
Path(os.path.join(DEFAULT_PATH,'static/userdata/csv')).mkdir(parents=True, exist_ok=True)
Path(os.path.join(DEFAULT_PATH,'static/userdata/pdf')).mkdir(parents=True, exist_ok=True)

# Get paths to SentencePiece model and vocab
LANG = os.getenv('PEARS_LANG') #default language for the installation
SPM_DEFAULT_VOCAB_PATH = f'app/api/models/{LANG}/{LANG}wiki.lite.16k.vocab'
spm_vocab_path = os.environ.get("SPM_VOCAB", SPM_DEFAULT_VOCAB_PATH)
SPM_DEFAULT_MODEL_PATH = f'app/api/models/{LANG}/{LANG}wiki.lite.16k.model'
spm_model_path = os.environ.get("SPM_MODEL", SPM_DEFAULT_MODEL_PATH)

# Define vector size
#from app.indexer.vectorizer import read_vocab
from app.readers import read_vocab, read_cosines
from sklearn.feature_extraction.text import CountVectorizer

print(f"Loading SPM vocab from '{spm_vocab_path}' ...")
vocab, inverted_vocab, logprobs = read_vocab(spm_vocab_path)
vectorizer = CountVectorizer(vocabulary=vocab, lowercase=True, token_pattern='[^ ]+')
VEC_SIZE = len(vocab)

# Load ft cosines
FT_DEFAULT_MODEL_PATH = f'app/api/models/{LANG}/{LANG}wiki.lite.16k.cos'
ft_path = os.environ.get("FT", FT_DEFAULT_MODEL_PATH)
ftcos = read_cosines(ft_path)

# Mail
mail = Mail(app)

# Define the database object which is imported
# by modules and controllers
db = SQLAlchemy(app)

# Load static multilingual info
from app.multilinguality import read_language_codes, read_stopwords

LANGUAGE_CODES = read_language_codes()
STOPWORDS = read_stopwords(LANGUAGE_CODES[LANG].lower())

# Import a module / component using its blueprint handler variable (mod_auth)
from app.indexer.controllers import indexer as indexer_module
from app.api.controllers import api as api_module
from app.search.controllers import search as search_module
from app.pod_finder.controllers import pod_finder as pod_finder_module
from app.orchard.controllers import orchard as orchard_module
from app.pages.controllers import pages as pages_module
from app.settings.controllers import settings as settings_module
from app.auth.controllers import auth as auth_module

# Register blueprint(s)
app.register_blueprint(indexer_module)
app.register_blueprint(api_module)
app.register_blueprint(search_module)
app.register_blueprint(pod_finder_module)
app.register_blueprint(orchard_module)
app.register_blueprint(pages_module)
app.register_blueprint(settings_module)
app.register_blueprint(auth_module)


# Build the database:
# This will create the database file using SQLAlchemy
# db.drop_all()
with app.app_context():
    db.create_all()

from flask_admin.contrib.sqla import ModelView
from app.api.models import Pods, Urls, User
from app.api.controllers import return_url_delete, return_pod_delete

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
            print("DELETING",model.url,model.vector)
            # Add your custom logic here and don't forget to commit any changes e.g.
            print(return_url_delete(model.url))
            self.session.commit()
        except Exception as ex:
            if not self.handle_view_exception(ex):
                flash(gettext('Failed to delete record. %(error)s', error=str(ex)), 'error')
                log.exception('Failed to delete record.')

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
                log.exception('Failed to delete record.')

            self.session.rollback()

            return False
        else:
            self.after_model_delete(model)

        return True

class UsersModelView(ModelView):
    list_template = 'admin/pears_list.html'
    column_exclude_list = ['password']
    column_searchable_list = ['email', 'username']
    can_edit = False
    page_size = 50
    form_widget_args = {
        'email': {
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

@app.cli.command('setadmin')
@click.argument('username')
def set_admin(username):
    '''Use from CLI with flask setadmin <username>.'''
    user = User.query.filter_by(username=username).first()
    user.is_admin = True
    db.session.commit()
    print(username,"is now admin.")

from app.indexer.controllers import progress_file
@app.cli.command('index')
def index():
    '''Index from the app/urls_to_index.txt file'''
    progress_file() 
