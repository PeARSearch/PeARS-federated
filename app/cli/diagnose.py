from app import app
from app.api.models import Urls

def check_sitename():
    '''
    Check whether the sitename in .env is consistent with the database.
    Otherwise, we will have issues with the first commandment
    "Do not cross-instance search yourself".
    '''
    urls = Urls.query.all()
    for u in urls:
        if 'pearslocal' not in u.share and app.config['SITENAME'] not in u.share:
            print(f"\nERROR: URL share is {u.share} but this instance's sitename is {app.config['SITENAME']}")
            print("It seems some of your database urls do not match the name of your instance.")
            print("This could cause issues when performing cross-instance search. Please double-check your SITENAME value in the .env file.")
            print("In case of issues with your share urls, you can easily rename part of them by using the CLI updateinstancename command.")

