from flask_wtf import FlaskForm
from wtforms import BooleanField, IntegerField, StringField, TextAreaField, PasswordField, HiddenField, URLField
from wtforms.validators import Length, NumberRange, Optional, DataRequired, InputRequired, EqualTo, Email, URL, ValidationError
from flask_babel import lazy_gettext


class URL_or_pearslocal(URL):
    """
    Validator that accepts real URLs as well as pearslocal strings
    """
    def __init__(self, *args):
        super().__init__(*args)

    def __call__(self, form, field):
        data = field.data or ""
        if data.startswith("pearslocal"):
            return
        super().__call__(form, field)


class SearchForm(FlaskForm):
    query = StringField("", [DataRequired()])

class RegistrationForm(FlaskForm):
    username = StringField(lazy_gettext('Username'), [Length(min=4, max=25, message=lazy_gettext("Your username should have between 4 and 25 characters."))])
    email = StringField(lazy_gettext('Email Address'), [DataRequired(), Email()])
    password = PasswordField(lazy_gettext('New Password'), [DataRequired(), Length(min=6, max=20, message=lazy_gettext("Your password should have between 6 and 20 characters.")), EqualTo('confirm', message=lazy_gettext('Passwords must match'))])
    confirm = PasswordField(lazy_gettext('Repeat Password'))
    captcha_id = HiddenField()
    captcha_answer = StringField(lazy_gettext("Captcha:"), [DataRequired()])
    accept_tos = BooleanField(lazy_gettext('I accept the TOS and Privacy statement'), [DataRequired()])

class LoginForm(FlaskForm):
    email = StringField(lazy_gettext('Email Address'), [DataRequired(), Email()])
    password = PasswordField(lazy_gettext('Password'), [DataRequired(), Length(min=6, max=20, message=lazy_gettext("Your password should have between 6 and 20 characters."))])

class PasswordForgottenForm(FlaskForm):
    email = StringField(lazy_gettext('Email Address'), [DataRequired(), Email()])

class PasswordChangeForm(FlaskForm):
    password = PasswordField(lazy_gettext('New Password'), [DataRequired(), Length(min=6, max=20, message=lazy_gettext("Your password should have between 6 and 20 characters.")), EqualTo('confirm', message=lazy_gettext('Passwords must match'))])
    confirm = PasswordField(lazy_gettext('Repeat Password'))

class EmailChangeForm(FlaskForm):
    email = StringField(lazy_gettext('New Email'), [DataRequired(), Email()])

class UsernameChangeForm(FlaskForm):
    username = StringField(lazy_gettext('New Username'), [Length(min=4, max=25, message=lazy_gettext("Your username should have between 4 and 25 characters."))])

class IndexerForm(FlaskForm):
    suggested_url = URLField(lazy_gettext('The url to index'), [DataRequired(), URL()], render_kw={"placeholder": lazy_gettext("The URL you would like to index.")})
    theme = StringField(lazy_gettext('Category'), [DataRequired(), Length(max=50)],  render_kw={"placeholder": lazy_gettext("A category for your URL. Start typing and suggestions will appear, but you can also write your own.")})
    snippet_length = IntegerField(lazy_gettext('Snippet length'), [NumberRange(min=-1, max=10_000)], render_kw={"value": 0})
    note = StringField(lazy_gettext('Optional note*'), [Length(max=1000)],  render_kw={"placeholder": lazy_gettext("Anything extra you would like people to know about this resource. (Max 1000 characters.)")})
    accept_tos = BooleanField(lazy_gettext('I confirm that my suggestion does not contravene the Terms of Service'), [DataRequired()])

class SuggestionForm(FlaskForm):
    suggested_url = URLField(lazy_gettext('Suggested url.'), [DataRequired(), URL()], render_kw={"placeholder": lazy_gettext("The URL you would like to suggest.")})
    theme = StringField(lazy_gettext('Category'), [DataRequired(), Length(max=50)],  render_kw={"placeholder": lazy_gettext("A category for your URL. Start typing and suggestions will appear, but you can also write your own.")})
    note = StringField(lazy_gettext('Optional note*'), [Length(max=1000)],  render_kw={"placeholder": lazy_gettext("Anything extra you would like people to know about this resource. (Max 1000 characters.)")})
    allows_reproduction = BooleanField(lazy_gettext("I believe this site has no/reduced copyright restrictions and allows reproducing extended text from it in PeARS (subject to checking by admins): "), [DataRequired()])
    captcha_id = HiddenField()
    captcha_answer = StringField(lazy_gettext("Captcha:"), [DataRequired()])

class ManualEntryForm(FlaskForm):
    title = StringField(lazy_gettext('A title for your entry'), [DataRequired(), Length(min=8, max=100, message=lazy_gettext("The title of your entry should have between 4 and 100 characters."))])
    related_url = URLField(lazy_gettext('An optional URL*'), [Optional(), URL()], render_kw={"placeholder": lazy_gettext("If you enter a URL in this field, your entry will automatically link to it.")})
    description = TextAreaField(lazy_gettext('Description'), [DataRequired(), Length(max=1000)],  render_kw={"placeholder": lazy_gettext("Anything extra you would like people to know about this resource. (Max 1000 characters.)")})
    snippet_length = IntegerField(lazy_gettext('Snippet length'), [NumberRange(min=-1, max=10_000)], render_kw={"value": 0})
    accept_tos = BooleanField(lazy_gettext('I confirm that my entry does not contravene the Terms of Service'), [DataRequired()])

class ReportingForm(FlaskForm):
    url = StringField(lazy_gettext('The url you are reporting'), [DataRequired(), URL_or_pearslocal()])
    report = TextAreaField(lazy_gettext('Description of the issue'), [DataRequired(), Length(max=1000)],  render_kw={"placeholder": lazy_gettext("Max 1000 characters.")})
    accept_tos = BooleanField(lazy_gettext('I confirm that I may be contacted in relation to my report.'), [DataRequired()])

class FeedbackForm(FlaskForm):
    report = TextAreaField(lazy_gettext('Your feedback'), [DataRequired(), Length(max=1000)],  render_kw={"placeholder": lazy_gettext("Max 1000 characters.")})
    accept_tos = BooleanField(lazy_gettext('I confirm that I may be contacted in relation to my report.'), [DataRequired()])

class AnnotationForm(FlaskForm):
    url = StringField(lazy_gettext('The url you wish to annotate'), [DataRequired(), URL_or_pearslocal()])
    note = TextAreaField(lazy_gettext('Your note (max 1000 characters)'), [DataRequired(), Length(max=1000)])
    accept_tos = BooleanField(lazy_gettext('I confirm that my comment can be openly published.'), [DataRequired()])
