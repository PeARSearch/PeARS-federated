def test_index_route(client):
    """Test that the index route returns a 200 status code."""
    response = client.get("/")
    assert response.status_code == 200
    assert b"Test Index Page" in response.data


def test_app_is_testing(app):
    """Test that the app is configured for testing."""
    assert app.config["TESTING"] == True
    assert app.config["SQLALCHEMY_DATABASE_URI"] == "sqlite:///:memory:"


def test_app_has_required_config(app):
    """Test that the app has the required configuration."""
    assert "LANGS" in app.config
    assert "en" in app.config["LANGS"]
