# SPDX-FileCopyrightText: 2024 PeARS Project, <community@pearsproject.org> 
#
# SPDX-License-Identifier: AGPL-3.0-only

import logging
from os import getenv, path
from glob import glob
from pathlib import Path
from os.path import join, dirname, realpath, isfile

# Import flask and template operators
from flask import Flask, flash, render_template, send_file, send_from_directory, request, abort
from flask_admin import Admin, AdminIndexView
from flask_mail import Mail

# Import SQLAlchemy and LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, current_user

dir_path = dirname(realpath(__file__))

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
app.config['SESSION_COOKIE_SECURE'] = True
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
app.config['USER-AGENT'] = "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; PeARSbot/0.1; +https://www.pearsproject.org/) Chrome/126.0.6478.114 Safari/537.36"

# Secrets
app.config['SECRET_KEY'] = getenv("SECRET_KEY")                         
app.config['SECURITY_PASSWORD_SALT'] = getenv("SECURITY_PASSWORD_SALT")
app.config['SESSION_COOKIE_HTTPONLY'] = False
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['CSRF_ENABLED'] = True
app.config['CSRF_SESSION_KEY'] = getenv("CSRF_SESSION_KEY")

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
app.config['FEEDBACK_FORM'] = True if getenv("FEEDBACK_FORM", "false").lower() == 'true' else False

# Localization
from flask_babel import Babel, gettext
app.config['LANGS'] = getenv('PEARS_LANGS', "en").split(',')
first_lang = app.config['LANGS'][0]
app.config['BABEL_DEFAULT_LOCALE'] = first_lang
app.config['BABEL_TRANSLATION_DIRECTORIES'] = getenv("TRANSLATION_DIR")
babel = Babel(app)

# Optimization
app.config['LIVE_MATRIX'] = True if getenv("LIVE_MATRIX", "false").lower() == 'true' else False
app.config['EXTEND_QUERY'] = True if getenv("EXTEND_QUERY", "false").lower() == 'true' else False

#Legacy
#app.config['MAX_PODS'] = int(getenv("MAX_PODS"))
#app.config['LOADED_POS_INDEX'] = int(getenv("LOADED_POS_INDEX"))

# Make sure user data directories exist
DEFAULT_PATH = dir_path
Path(path.join(DEFAULT_PATH,'userdata')).mkdir(parents=True, exist_ok=True)
if getenv("SUGGESTIONS_DIR", "") != "":
    Path(getenv("SUGGESTIONS_DIR")).mkdir(parents=True, exist_ok=True)

# Mail
mail = Mail(app)


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

@app.route('/static/assets/<path:path>')
def serve_logos(path):
    return send_from_directory(app.config['LOGO_PATH'], path)


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
    models[LANG]['stopwords'] = read_stopwords(LANGUAGE_CODES[LANG].lower())

# All vocabs have the same vector size
VEC_SIZE = len(models[first_lang]['vocab'])

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
    for LANG in app.config['LANGS']:
        npzs = glob(join(pod_dir,'*',LANG,'*.u.*npz'))
        if len(npzs) == 0:
            continue
        m, bins, podnames, urls = mk_vec_matrix(LANG)
        models[LANG]['m'] = m
        models[LANG]['mbins'] = bins
        models[LANG]['podnames'] = podnames
        models[LANG]['urls'] = urls

# Legacy
#if app.config['LOADED_POS_INDEX'] > 0:
#    from app.indexer.posix import load_posindices
#    for LANG in LANGS:
#        models[LANG]['posix'] = load_posindices(LANG, n=app.config['LOADED_POS_INDEX'])


#######
# Admin
#######

from flask_admin.contrib.sqla import ModelView
from app.api.models import Pods, Urls, User, Personalization, Suggestions
from app.utils_db import delete_url_representations, delete_pod_representations, \
        rm_from_npz, add_to_npz, create_pod_in_db, create_pod_npz_pos, rm_doc_from_pos, update_db_idvs_after_npz_delete

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
        if current_user.is_authenticated and current_user.is_admin:
            return True # This does the trick rendering the view only if the user is admin
        else:
            return abort(404)


admin = Admin(app, name='PeARS DB', template_mode='bootstrap3', index_view=MyAdminIndexView())

class UrlsModelView(ModelView):
    list_template = 'admin/pears_list.html'
    column_hide_backrefs = False
    column_list = ['url', 'title', 'pod', 'notes']
    column_searchable_list = ['url', 'title', 'pod', 'notes']
    can_edit = True
    page_size = 100
    form_widget_args = {
        'vector': {
            'readonly': True
        },
        'url': {
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

    def update_model(self, form, model):
        """
            Update model from form.
        """
        try:
            # at this point model variable has the unmodified values
            old_pod = model.pod
            _, contributor = old_pod.split('.u.')
            if '.u.' not in form.pod.data:
                form.pod.data+='.u.'+contributor
            new_pod = form.pod.data
            new_theme = new_pod.split('.u.')[0]
            p = db.session.query(Pods).filter_by(name=old_pod).first()
            lang = p.language
            form.populate_obj(model)

            # at this point model variable has the form values
            # your on_model_change is called
            self._on_model_change(form, model, False)

            # model is now being committed
            self.session.commit()
        except Exception as ex:
            if not self.handle_view_exception(ex):
                flash(gettext('Failed to update record. %(error)s', error=str(ex)), 'error')
            self.session.rollback()
            return False
        else:
            # model is now committed to the database
            if old_pod != new_pod:
                print(f"Pod name has changed from {old_pod} to {new_pod}!")
                print("Move vector in npz file")
                try:
                    pod_path = create_pod_npz_pos(contributor, new_theme, lang)
                    create_pod_in_db(contributor, new_theme, lang)
                    idv, v = rm_from_npz(model.vector, old_pod)
                    update_db_idvs_after_npz_delete(idv, old_pod)
                    add_to_npz(v, pod_path+'.npz')
                    #Removing from pos but not re-adding since current version does not make use of positional index. To fix.
                    rm_doc_from_pos(model.id, old_pod)
                    self.session.commit()
                    #If pod empty, delete
                    if len(db.session.query(Urls).filter_by(pod=old_pod).all()) == 0:
                        delete_pod_representations(old_pod)

                except Exception as ex:
                    if not self.handle_view_exception(ex):
                        flash(gettext('Failed to update record. %(error)s', error=str(ex)), 'error')
                    self.session.rollback()
                    return False
            self.after_model_change(form, model, False)
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
            delete_pod_representations(model.name)
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

class PersonalizationModelView(ModelView):
    list_template = 'admin/pears_list.html'
    column_searchable_list = ['feature', 'language']
    can_edit = True
    page_size = 50

class SuggestionsModelView(ModelView):
    list_template = 'admin/pears_list.html'
    column_searchable_list = ['url', 'pod']
    can_edit = True
    page_size = 50

admin.add_view(PodsModelView(Pods, db.session))
admin.add_view(UrlsModelView(Urls, db.session))
admin.add_view(UsersModelView(User, db.session))
admin.add_view(PersonalizationModelView(Personalization, db.session))
admin.add_view(SuggestionsModelView(Suggestions, db.session))

@app.errorhandler(404)
def page_not_found(e):
    # note that we set the 404 status explicitly
    flash("404. Page not found. Please return to search page.")
    return render_template("404.html"), 404

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
