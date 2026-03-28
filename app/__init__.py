# SPDX-FileCopyrightText: 2025 PeARS Project, <community@pearsproject.org> 
#
# SPDX-License-Identifier: AGPL-3.0-only

import logging
import threading
from os import getenv, path
from os.path import join, dirname, realpath, isfile
from glob import glob
from pathlib import Path

import numpy as np
from flask import Flask, flash, render_template, send_file, send_from_directory, request, abort, url_for
from flask_admin import Admin, AdminIndexView
from flask_login import current_user

from app.extensions import db, migrate, mail, login_manager
from app.init_logging import run_logging

dir_path = dirname(realpath(__file__))

# Module-level state populated by create_app when LOAD_MODELS is True.
# Other modules import these; they remain empty dicts/defaults in testing.
models = {}
LANGUAGE_CODES = {}
VEC_SIZE = 0
DEFAULT_PATH = dir_path
mail_logger = run_logging()

# Decentralized search state (populated in background thread)
instances = []
M = np.array([])


def create_app(config_name=None):
    """Application factory.

    Args:
        config_name: One of 'development', 'testing', 'production', or None.
                     None falls back to FLASK_ENV or 'development'.
    """
    global models, LANGUAGE_CODES, VEC_SIZE, DEFAULT_PATH, instances, M

    app = Flask(__name__, static_folder='static')

    # --- Configuration ---------------------------------------------------
    from config import config_by_name
    if config_name is None:
        config_name = getenv('FLASK_ENV', 'development')
    app.config.from_object(config_by_name.get(config_name, config_by_name['default']))

    # Apply env-var overrides (mail, secrets, legal, etc.) for non-test runs
    if not app.config.get('TESTING'):
        from app.init_config import run_config
        app = run_config(app)
    else:
        # Set keys that init_config would normally provide
        app.config.setdefault('USER-AGENT', 'PeARSbot-test/0.1')

    # --- Extensions ------------------------------------------------------
    db.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)
    login_manager.init_app(app)

    # --- Babel -----------------------------------------------------------
    from flask_babel import Babel, gettext
    Babel(app)

    # --- User data directories -------------------------------------------
    DEFAULT_PATH = dir_path
    Path(path.join(DEFAULT_PATH, 'userdata')).mkdir(parents=True, exist_ok=True)
    if getenv("SUGGESTIONS_DIR", "") != "":
        Path(getenv("SUGGESTIONS_DIR")).mkdir(parents=True, exist_ok=True)

    # --- Branding --------------------------------------------------------
    app.config['OWN_BRAND'] = (
        True if getenv('OWN_BRAND', str(app.config.get('OWN_BRAND', 'false'))).lower() == 'true'
        else False
    )
    logo_path = getenv('LOGO_PATH', '')
    if logo_path != '' and isfile(join(logo_path, "logo.png")):
        app.config['LOGO_PATH'] = logo_path
    else:
        app.config['LOGO_PATH'] = join(dir_path, 'static', 'assets')

    @app.context_processor
    def inject_brand():
        return dict(own_brand=app.config['OWN_BRAND'], logo_path=app.config['LOGO_PATH'])

    @app.route('/static/assets/<path:path>')
    def serve_logos(path):
        return send_from_directory(app.config['LOGO_PATH'], path)

    # --- Load pretrained models (skip in testing) ------------------------
    if app.config.get('LOAD_MODELS', True):
        _load_models(app)

    # --- Database --------------------------------------------------------
    # Import models so SQLAlchemy knows about them before create_all
    from app.api.models import Pods, Urls, User, Personalization, Suggestions, RejectedSuggestions  # noqa: F811

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # --- Blueprints ------------------------------------------------------
    from app.indexer.controllers import indexer as indexer_module
    from app.api.controllers import api as api_module
    from app.search.controllers import search as search_module
    from app.orchard.controllers import orchard as orchard_module
    from app.pages.controllers import pages as pages_module
    from app.settings.controllers import settings as settings_module
    from app.auth.controllers import auth as auth_module
    from app.cli.controllers import pears as pears_module

    app.register_blueprint(indexer_module)
    app.register_blueprint(api_module)
    app.register_blueprint(search_module)
    app.register_blueprint(orchard_module)
    app.register_blueprint(pages_module)
    app.register_blueprint(settings_module)
    app.register_blueprint(auth_module)
    app.register_blueprint(pears_module)

    # --- Create tables ---------------------------------------------------
    with app.app_context():
        db.create_all()

    # --- Maintenance mode ------------------------------------------------
    @app.before_request
    def check_under_maintenance():
        from app.settings.controllers import get_maintance_mode
        if _reroute_for_maintenance(request.path, get_maintance_mode):
            abort(503)

    # --- Optimization (pre-compute matrices) -----------------------------
    if app.config.get('LOAD_MODELS', True) and not app.config.get('LIVE_MATRIX', True):
        _precompute_matrices(app)

    # --- Decentralized search (background thread) ------------------------
    if not app.config.get('TESTING'):
        _start_instance_loader(app)

    # --- Admin interface -------------------------------------------------
    _register_admin(app)

    # --- Error handlers & misc routes ------------------------------------
    @app.errorhandler(404)
    def page_not_found(e):
        flash("The page that you are trying to access doesn't exist or you don't have sufficient permissions to access it. If you're not logged in, log in and try accessing the page again. If you're sure the page exists and that you should have access to it, contact the administrators.", "warning")
        return render_template("404.html"), 404

    @app.errorhandler(503)
    def maintenance_mode_handler(e):
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

    return app


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_models(app):
    """Load ML vocabulary and cosine models for each configured language."""
    global models, LANGUAGE_CODES, VEC_SIZE

    from app.readers import read_vocab, read_cosines
    from app.multilinguality import read_language_codes, read_stopwords
    from sklearn.feature_extraction.text import CountVectorizer

    LANGUAGE_CODES = read_language_codes()
    models = {}
    for lang in app.config['LANGS']:
        models[lang] = {}
        spm_vocab_path = f'app/api/models/{lang}/{lang}wiki.16k.vocab'
        ft_path = f'app/api/models/{lang}/{lang}wiki.16k.cos'
        vocab, inverted_vocab, logprobs = read_vocab(spm_vocab_path)
        vectorizer = CountVectorizer(vocabulary=vocab, lowercase=True, token_pattern='[^ ]+')
        ftcos = read_cosines(ft_path)
        models[lang]['vocab'] = vocab
        models[lang]['inverted_vocab'] = inverted_vocab
        models[lang]['logprobs'] = logprobs
        models[lang]['vectorizer'] = vectorizer
        models[lang]['nns'] = ftcos
        if lang in LANGUAGE_CODES:
            models[lang]['stopwords'] = read_stopwords(LANGUAGE_CODES[lang].lower())
        else:
            models[lang]['stopwords'] = []

    first_lang = app.config['LANGS'][0]
    VEC_SIZE = len(models[first_lang]['vocab'])


def _precompute_matrices(app):
    """Pre-compute search matrices when LIVE_MATRIX is False."""
    global models
    from app.search.score_pages import mk_vec_matrix

    pod_dir = getenv("PODS_DIR", join(dir_path, 'pods'))
    for lang in app.config['LANGS']:
        npzs = glob(join(pod_dir, '*', lang, '*.u.*npz'))
        if len(npzs) == 0:
            continue
        m, bins, podnames, urls = mk_vec_matrix(lang)
        models[lang]['m'] = m
        models[lang]['mbins'] = bins
        models[lang]['podnames'] = podnames
        models[lang]['urls'] = urls


def _start_instance_loader(app):
    """Load remote instance data in a background thread."""
    global instances, M

    def _load():
        global instances, M
        with app.app_context():
            try:
                from app.search.cross_instance_search import filter_instances_by_language
                instances, M, skipped = filter_instances_by_language()
                if skipped:
                    for s in skipped:
                        logging.warning(f"Skipped remote instance {s['instance']}: {s['reason']}")
                logging.info(f"Loaded {len(instances)} remote instance(s) in background.")
            except Exception as e:
                logging.error(f"Failed to load remote instances: {e}")

    loader = threading.Thread(target=_load, daemon=True)
    loader.start()

    _sitename_check_completed = False

    @app.before_request
    def check_sitename_and_hostname():
        nonlocal _sitename_check_completed
        if not _sitename_check_completed:
            host_url = url_for("search.index", _external=True)
            if host_url.rstrip("/") != app.config["SITENAME"]:
                logging.error("`host_url` and `SITENAME` do not match -- this can cause errors, correct this unless you know what you are doing!")
            _sitename_check_completed = True


def _reroute_for_maintenance(req_path, get_maintance_mode_fn):
    """Check if request should be rerouted to maintenance page."""
    if not get_maintance_mode_fn():
        return False
    if req_path in [url_for('settings.toggle_maintenance_mode'), url_for('auth.login'), url_for('auth.logout')]:
        return False
    if '/static/' in req_path:
        return False
    return True


def _register_admin(app):
    """Set up Flask-Admin views."""
    from flask_admin.contrib.sqla.view import ModelView
    from flask_babel import gettext
    from app.api.models import Pods, Urls, User, Personalization, Suggestions, RejectedSuggestions
    from app.utils_db import (delete_url_representations, delete_pod_representations,
                              rm_from_npz, add_to_npz, create_pod_in_db, create_pod_npz_pos,
                              rm_doc_from_pos, update_db_idvs_after_npz_delete)

    def can_access_flaskadmin():
        if not current_user.is_authenticated:
            return abort(404)
        if not current_user.is_admin:
            return abort(404)
        return True

    class MyAdminIndexView(AdminIndexView):
        def is_accessible(self):
            return can_access_flaskadmin()

    admin = Admin(app, name='PeARS DB', index_view=MyAdminIndexView())

    class UrlsModelView(ModelView):
        list_template = 'admin/pears_list.html'
        column_list = ['url', 'title', 'pod', 'notes']
        column_searchable_list = ['url', 'title', 'pod', 'notes']
        can_edit = True
        page_size = 100
        form_widget_args = {
            'vector': {'readonly': True},
            'url': {'readonly': True},
            'date_created': {'readonly': True},
            'date_modified': {'readonly': True},
        }
        def is_accessible(self):
            return can_access_flaskadmin()
        def delete_model(self, model):
            try:
                self.on_model_delete(model)
                print("DELETING", model.url)
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
            try:
                old_pod = model.pod
                _, contributor = old_pod.split('.u.')
                if '.u.' not in form.pod.data:
                    form.pod.data += '.u.' + contributor
                new_pod = form.pod.data
                new_theme = new_pod.split('.u.')[0]
                p = db.session.query(Pods).filter_by(name=old_pod).first()
                lang = p.language
                form.populate_obj(model)
                self._on_model_change(form, model, False)
                self.session.commit()
            except Exception as ex:
                if not self.handle_view_exception(ex):
                    flash(gettext('Failed to update record. %(error)s', error=str(ex)), 'error')
                self.session.rollback()
                return False
            else:
                if old_pod != new_pod:
                    try:
                        pod_path = create_pod_npz_pos(contributor, new_theme, lang)
                        create_pod_in_db(contributor, new_theme, lang)
                        idv, v = rm_from_npz(model.vector, old_pod)
                        update_db_idvs_after_npz_delete(idv, old_pod)
                        add_to_npz(v, pod_path + '.npz')
                        rm_doc_from_pos(model.id, old_pod)
                        self.session.commit()
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
        column_exclude_list = ['DS_vector', 'word_vector']
        column_searchable_list = ['url', 'name', 'description', 'language']
        can_edit = False
        page_size = 50
        form_widget_args = {
            'DS_vector': {'readonly': True},
            'word_vector': {'readonly': True},
            'date_created': {'readonly': True},
            'date_modified': {'readonly': True},
        }
        def is_accessible(self):
            return can_access_flaskadmin()
        def delete_model(self, model):
            try:
                self.on_model_delete(model)
                print("DELETING", model.name)
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
            'email': {'readonly': True},
            'password': {'readonly': True},
            'username': {'readonly': True},
            'is_confirmed': {'readonly': True},
            'confirmed_on': {'readonly': True},
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
