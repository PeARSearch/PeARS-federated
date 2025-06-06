import os
from unittest.mock import patch

from flask import Flask, request


def create_test_app():
    """Create a Flask app instance specifically for testing.

    Since the main app doesn't use the factory pattern, we need to
    create a simplified version for testing that doesn't rely on
    all the complex initializations.
    """
    # Set testing environment variables
    os.environ.setdefault("FLASK_ENV", "testing")
    os.environ.setdefault("BABEL_DEFAULT_LOCALE", "en")
    os.environ.setdefault("BABEL_DEFAULT_TIMEZONE", "UTC")

    # Create a simple Flask app for testing
    app = Flask(__name__)
    app.config.update(
        {
            "TESTING": True,
            "SECRET_KEY": "test-key",
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "BABEL_DEFAULT_LOCALE": "en",
            "BABEL_DEFAULT_TIMEZONE": "UTC",
            "LANGS": ["en"],
        }
    )

    # Add a simple route for testing
    @app.route("/")
    def index():
        return "Test Index Page"

    return app


def create_api_test_app():
    """Create a Flask app instance specifically for API testing.

    This provides a completely fresh app instance with API endpoints
    already configured.
    """
    app = Flask(__name__)
    app.config.update(
        {
            "TESTING": True,
            "SECRET_KEY": "api-test-key",
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "WTF_CSRF_ENABLED": False,
        }
    )

    # Add API test endpoints
    @app.route("/api/test", methods=["GET"])
    def test_endpoint():
        return {"status": "success", "message": "API is working"}, 200

    @app.route("/api/search", methods=["GET"])
    def search_endpoint():
        query = request.args.get("q", "")
        if not query:
            return {"status": "error", "message": "Query cannot be empty"}, 400
        return {"status": "success", "results": [f"Result for {query}"]}, 200

    return app
