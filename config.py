# SPDX-FileCopyrightText: 2023 PeARS Project <community@pearsproject.org>
#
# SPDX-License-Identifier: AGPL-3.0-only

import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class BaseConfig:
    DEBUG = False
    TESTING = False
    SQLALCHEMY_DATABASE_URI = os.getenv(
        'SQLALCHEMY_DATABASE_URI',
        'sqlite:///' + os.path.join(BASE_DIR, 'app.db'),
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    THREADS_PER_PAGE = 2

    # Controls whether ML models are loaded at startup.
    # Disable in tests to avoid needing model files on disk.
    LOAD_MODELS = True


class DevelopmentConfig(BaseConfig):
    DEBUG = True


class TestingConfig(BaseConfig):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    LOAD_MODELS = False
    LIVE_MATRIX = False
    EXTEND_QUERY = False

    # Dummy values so init_config doesn't blow up on missing env vars
    SECRET_KEY = 'test-secret-key'
    SECURITY_PASSWORD_SALT = 'test-salt'
    CSRF_SESSION_KEY = 'test-csrf'
    SITENAME = 'http://localhost'
    SITE_TOPIC = 'testing'
    SEARCH_PLACEHOLDER = 'test search'
    LANGS = ['en']
    BABEL_DEFAULT_LOCALE = 'en'
    BABEL_TRANSLATION_DIRECTORIES = 'translations'
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

    # User-Agent
    USER_AGENT = 'PeARSbot-test/0.1'


class ProductionConfig(BaseConfig):
    pass


# Legacy flat config values for backward compatibility with
# app.config.from_object('config')
DEBUG = True
SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(BASE_DIR, 'app.db')
DATABASE_CONNECT_OPTIONS = {}
THREADS_PER_PAGE = 2
SQLALCHEMY_TRACK_MODIFICATIONS = False


config_by_name = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig,
}

