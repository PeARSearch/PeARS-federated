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
