# SPDX-FileCopyrightText: 2023 PeARS Project <community@pearsproject.org>
#
# SPDX-License-Identifier: AGPL-3.0-only

import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class TestingConfig:
    """Config used when _PEARS_CONFIG=testing is set."""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = False
    LOAD_MODELS = False
    LIVE_MATRIX = False
    EXTEND_QUERY = False

    SECRET_KEY = 'test-secret-key'
    SECURITY_PASSWORD_SALT = 'test-salt'
    CSRF_SESSION_KEY = 'test-csrf'
    SITENAME = 'http://localhost'
    SITE_TOPIC = 'testing'
    SEARCH_PLACEHOLDER = 'test search'
    LANGS = ['en']
    BABEL_DEFAULT_LOCALE = 'en'
    BABEL_TRANSLATION_DIRECTORIES = os.path.join(BASE_DIR, 'translations')
    MAIL_ENABLED = False
    MAIL_DEFAULT_SENDER = 'test@test.com'
    MAIL_SERVER = 'localhost'
    MAIL_PORT = 25
    NEW_USERS = True
    FEEDBACK_FORM = False
    SNIPPET_LENGTH = 10
    OWN_BRAND = False

    # Legal
    ORG_NAME = 'Test Org'
    ORG_ADDRESS = '123 Test St'
    ORG_EMAIL = 'org@test.com'
    APPLICABLE_LAW = 'Test Jurisdiction'
    TAX_OFFICE = 'N/A'
    REGISTRATION_NUMBER = 'N/A'
    VAT_NUMBER = 'N/A'
    EU_SPECIFIC = False
    SERVERS = 'Test Servers'


# Legacy flat config values used by app.config.from_object('config')
DEBUG = os.getenv('FLASK_ENV', 'production') == 'development'
SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(BASE_DIR, 'app.db')
DATABASE_CONNECT_OPTIONS = {}
THREADS_PER_PAGE = 2
SQLALCHEMY_TRACK_MODIFICATIONS = False

