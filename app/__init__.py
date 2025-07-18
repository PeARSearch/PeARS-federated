# SPDX-FileCopyrightText: 2025 PeARS Project, <community@pearsproject.org> 
#
# SPDX-License-Identifier: AGPL-3.0-only

from os import getenv, path
from glob import glob
from pathlib import Path
from os.path import join, dirname, realpath, isfile
import logging

# Import flask and template operators
from flask import Flask, flash, render_template, send_file, send_from_directory, request, abort, url_for
from flask_admin import Admin, AdminIndexView
from flask_mail import Mail

# Import SQLAlchemy and LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, current_user

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

from app.init_config import run_config
from flask_babel import Babel, gettext
app = run_config(app)
first_lang = app.config['LANGS'][0]
babel = Babel(app)

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

@app.context_processor
def inject_single_pod_indexing_vars():
    """Inject variables related to single pod indexing status
    """
    return {
        "single_pod_indexing": app.config["SINGLE_POD_INDEXING"],
        "single_pod_name": app.config["SINGLE_POD_NAME"]
    }

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
    if LANG in LANGUAGE_CODES:
        models[LANG]['stopwords'] = read_stopwords(LANGUAGE_CODES[LANG].lower())
    else:
        models[LANG]['stopwords'] = []

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

instances, M, _  = filter_instances_by_language()

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

from flask_admin.contrib.sqla import ModelView
from app.api.models import Pods, Urls, User, Personalization, Suggestions, RejectedSuggestions
from app.utils_db import delete_url_representations, delete_pod_representations, \
        rm_from_npz, add_to_npz, create_pod_in_db, create_pod_npz_pos, rm_doc_from_pos, update_db_idvs_after_npz_delete

from flask_admin import expose
from flask_admin.contrib.sqla.view import ModelView
from flask_admin.model.template import EndpointLinkRowAction


# Single-pod instance check
if app.config['SINGLE_POD_INDEXING']:
    with app.app_context():
        all_pods = db.session.query(Pods).all()
        if any(pod for pod in all_pods if not pod.name.startswith(f"{app.config['SINGLE_POD_NAME']}.l.")):
            raise ValueError("Non-global pods detected. Please repopulate your instance or turn off the SINGLE_POD_INDEXING flag.") 

# Authentification
class MyLoginManager(LoginManager):
    def unauthorized(self):
        return abort(404)        

login_manager = MyLoginManager()
login_manager.login_view = 'auth.login'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    # since the user_id is just the primary key of our user table, use it in the query for the user
    return User.query.get(int(user_id))



# Flask and Flask-SQLAlchemy initialization here

def can_access_flaskadmin():
    if not current_user.is_authenticated:
        return abort(404)
    if not current_user.is_admin:
        return abort(404)
    return True

class MyAdminIndexView(AdminIndexView):
    def is_accessible(self):
        return can_access_flaskadmin()


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
    def is_accessible(self):
        return can_access_flaskadmin()
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
            theme, lang_and_user = old_pod.split(".l.")
            language, contributor = lang_and_user.split('.u.')
            if '.u.' not in form.pod.data:
                form.pod.data+='.u.'+contributor
            if '.l.' not in form.pod.data:
                _theme, _user = form.pod.data.split(".u.")
                form.pod.data = _theme + ".l." + language + ".u." + _user
            new_pod = form.pod.data
            new_theme, new_lang_and_user = new_pod.split('.l.')
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
    def is_accessible(self):
        return can_access_flaskadmin()
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
    def is_accessible(self):
        return can_access_flaskadmin()

class PersonalizationModelView(ModelView):
    list_template = 'admin/pears_list.html'
    column_searchable_list = ['feature', 'language']
    can_edit = True
    page_size = 50
    def is_accessible(self):
        return can_access_flaskadmin()

class SuggestionsModelView(ModelView):
    list_template = 'admin/pears_list.html'
    column_searchable_list = ['url', 'pod']
    can_edit = True
    page_size = 50
    def is_accessible(self):
        return can_access_flaskadmin()

class RejectedSuggestionsModelView(ModelView):
    list_template = 'admin/pears_list.html'
    column_searchable_list = ['url', 'pod', 'rejection_reason']
    can_edit = True
    page_size = 50
    def is_accessible(self):
        return can_access_flaskadmin()


admin.add_view(PodsModelView(Pods, db.session))
admin.add_view(UrlsModelView(Urls, db.session))
admin.add_view(UsersModelView(User, db.session))
admin.add_view(PersonalizationModelView(Personalization, db.session))
admin.add_view(SuggestionsModelView(Suggestions, db.session))
admin.add_view(RejectedSuggestionsModelView(RejectedSuggestions, db.session))


@app.errorhandler(404)
def page_not_found(e):
    flash("The page that you are trying to access doesn't exist or you don't have sufficient permissions to access it. If you're not logged in, log in and try accessing the page again. If you're sure the page exists and that you should have access to it, contact the administrators.")
    return render_template("404.html"), 404

@app.errorhandler(503)
def maintenance_mode(e):
    flash("We are doing some (hopefully) quick maintenance on this instance. Please check back later!")
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
