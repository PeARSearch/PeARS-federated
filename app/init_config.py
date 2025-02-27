from os import getenv
from dotenv import load_dotenv

def run_config(app):
    app.config.from_object('config')

    load_dotenv()
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
    app.config['SESSION_COOKIE_SECURE'] = True
    app.config['SESSION_COOKIE_HTTPONLY'] = False
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['CSRF_ENABLED'] = True
    app.config['CSRF_SESSION_KEY'] = getenv("CSRF_SESSION_KEY")

    # Legal
    app.config['ORG_NAME'] = getenv("ORG_NAME", None)
    app.config['ORG_ADDRESS'] = getenv("ORG_ADDRESS", None)
    app.config['ORG_EMAIL'] = getenv("ORG_EMAIL", None)
    app.config['TAX_OFFICE'] = getenv("TAX_OFFICE", None)
    app.config['VAT_NUMBER'] = getenv("VAT_NUMBER", None)
    app.config['REGISTRATION_NUMBER'] = getenv("REGISTRATION_NUMBER", None)
    app.config['APPLICABLE_LAW'] = getenv("APPLICABLE_LAW", None)
    app.config['SERVERS'] = getenv("SERVERS", None)
    app.config['EU_SPECIFIC'] = True if getenv("EU_SPECIFIC", "false").lower() == 'true' else False
    app.config['SNIPPET_LENGTH'] = int(getenv("SNIPPET_LENGTH"))

    # User-related settings
    app.config['NEW_USERS'] = True if getenv("NEW_USERS_ALLOWED", "false").lower() == 'true' else False
    app.config['FEEDBACK_FORM'] = True if getenv("FEEDBACK_FORM", "false").lower() == 'true' else False

    # Localization
    app.config['LANGS'] = getenv('PEARS_LANGS', "en").split(',')
    app.config['BABEL_DEFAULT_LOCALE'] = app.config['LANGS'][0]
    app.config['BABEL_TRANSLATION_DIRECTORIES'] = getenv("TRANSLATION_DIR")

    # Optimization
    app.config['LIVE_MATRIX'] = True if getenv("LIVE_MATRIX", "false").lower() == 'true' else False
    app.config['EXTEND_QUERY'] = True if getenv("EXTEND_QUERY", "false").lower() == 'true' else False
    return app
