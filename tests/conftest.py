import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# Add the parent directory to path so that app can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tests.test_utils import create_test_app

# Set up environment before importing from app
os.environ["BABEL_DEFAULT_LOCALE"] = "en"
os.environ["BABEL_DEFAULT_TIMEZONE"] = "UTC"

# We need to patch Flask-Babel before it gets imported
sys.modules["flask_babel"] = MagicMock()
sys.modules["flask_babel"].Babel = MagicMock()

# Language setting
os.environ["PEARS_LANGS"] = "en"
os.environ["TRANSLATION_DIR"] = "translations"

# Mail Settings
os.environ["MAIL_DEFAULT_SENDER"] = "test@test.com"
os.environ["EMAIL_USER"] = "test@test.com"
os.environ["MAIL_SERVER"] = "smtp.test.com"
os.environ["MAIL_PORT"] = "587"
os.environ["EMAIL_PASSWORD"] = "test"

# Secrets
os.environ["SECRET_KEY"] = "test"
os.environ["SECURITY_PASSWORD_SALT"] = "test"
os.environ["CSRF_SESSION_KEY"] = "test"

# Docker settings
os.environ["PODS_DIR"] = "pods"
os.environ["CAPTCHA_DIR"] = "captchas"

# Server
os.environ["APP_PORT"] = "8080"
os.environ["FLASK_ENV"] = (
    "development"  # Set this to "production", when running flask in production.
)

# About you
os.environ["OWN_BRAND"] = "false"
os.environ["SITENAME"] = "https://my-first-pears-instance.org"
os.environ["SITE_TOPIC"] = (
    "a brief description of the focus of your instance, to appear in the FAQ page"
)
os.environ["SEARCH_PLACEHOLDER"] = (
    "a placeholder with some examples of what people can search for, will appear in main search bar"
)

# Legal
os.environ["ORG_NAME"] = "your organisation's name"
os.environ["ORG_ADDRESS"] = "your organisation's address, on one line"
os.environ["ORG_EMAIL"] = "your organisation's email (could be the same as above)"
os.environ["APPLICABLE_LAW"] = "your jurisdiction (usually, your location)"
os.environ["TAX_OFFICE"] = "if applicable"
os.environ["REGISTRATION_NUMBER"] = "for organisations or companies, if applicable"
os.environ["VAT_NUMBER"] = "if applicable"
os.environ["EU_SPECIFIC"] = "true if server is located in the EU, false otherwise"
os.environ["SERVERS"] = (
    "the organisation providing the servers on which the instance is hosted"
)

# User-related settings
os.environ["NEW_USERS_ALLOWED"] = "allow users to create accounts"
os.environ["FEEDBACK_FORM"] = "false"

# Snippet length is fixed at 10 words to respect EU legal framework
# Do not change this unless you know what you are doing!
os.environ["SNIPPET_LENGTH"] = "10"

# Optimization
os.environ["LIVE_MATRIX"] = "true"
os.environ["EXTEND_QUERY"] = "false"


@pytest.fixture(scope="session")
def app():
    """Create and configure a Flask app for testing."""
    app = create_test_app()

    # Setup app context
    with app.app_context():
        yield app


@pytest.fixture(scope="function")
def client(app):
    """A test client for the app."""
    with app.test_client() as client:
        yield client


@pytest.fixture(scope="function")
def runner(app):
    """A test CLI runner for the app."""
    return app.test_cli_runner()
