# SPDX-FileCopyrightText: 2023 PeARS Project <community@pearsproject.org>
#
# SPDX-License-Identifier: AGPL-3.0-only

from decouple import config
import os

# Statement for enabling the development environment
DEBUG = True

# Define the application directory
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Define the database - we are working with
# SQLite for this example
SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(BASE_DIR, 'app.db')
DATABASE_CONNECT_OPTIONS = {}

# Application threads. A common general assumption is
# using 2 per available processor cores - to handle
# incoming requests using one and performing background
# operations using the other.
THREADS_PER_PAGE = 2

# Enable protection agains *Cross-site Request Forgery (CSRF)*
CSRF_ENABLED = True

# Use a secure, unique and absolutely secret key for
# signing the data.
CSRF_SESSION_KEY = "secret"

# Secrets
SECRET_KEY = config("SECRET_KEY", default="very-important")
SECURITY_PASSWORD_SALT = config("SECURITY_PASSWORD_SALT", default="very-important")

SQLALCHEMY_TRACK_MODIFICATIONS = False

# Mail Settings
MAIL_DEFAULT_SENDER = "<your email address>"
MAIL_SERVER = "<your email server>"
MAIL_PORT = 587
MAIL_USE_TLS = True
MAIL_USE_SSL = False
MAIL_DEBUG = False
MAIL_USERNAME = os.getenv("EMAIL_USER")
MAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
