import os
import glob
import json
import time
import datetime

import bs4
from mastodon import Mastodon
from mastodon.errors import MastodonUnauthorizedError

from app import app
from app.utils_db import create_suggestion_in_db

if not os.path.isdir(".mastodon"):
    os.mkdir(".mastodon")

# Create an instance of the Mastodon class
mastodon = Mastodon(
    access_token=app.config["MASTODON_API_TOKEN"],
    api_base_url='https://hol.ogra.ph/'
)

def handle_mention(status):
    bot_username = app.config["MASTODON_USERNAME"]
    if bot_username in status.content and "pearsbot-suggest" in status.content:
        mastodon.status_post("'@' + status.account.username + ' pearsbot is not working yet [[automated message]]'")

def process_new_notifications():

    for n in mastodon.notifications():
        # we only look at mentions
        if n.type != "mention":
            continue

        # only with linked statuses
        if not n.status or not n.status.in_reply_to_id:
            continue

        # ignore already processed mentions
        notification_id = n.id
        if os.path.isfile(f".mastodon/{n.id}.txt"):
            continue

        if "pearsbot-suggest" in n.status.content:
            try:
                reply = mastodon.status(n.status.in_reply_to_id)
                soup = bs4.BeautifulSoup(reply.content, features="lxml")
                print(soup)
                links = soup.findAll("a")
                print(links)
                if not links:
                    link = None
                else:
                    link = links[-1]["href"]
            except MastodonUnauthorizedError as e:
                link = None
                print(e.message)

            if link:
                create_suggestion_in_db(link, "mastodon-bot-suggestions", f"from {n.status.uri}", "mastodon-bot")

                mastodon.status_post(f"Thanks for your suggestion! I recorded the URL {link}. (Is this not what you intended? You can manually submit the correct URL instead - see link in bio.) The URL will be added to the index if the admins approve it, usually this happens within 48 hours.", in_reply_to_id=n.status.id)
            
            else:
                mastodon.status_post("Sorry, couldn't find a link in this post. Submit your URL manually or contact the admins - see link in bio.")

            with open(f".mastodon/{n.id}.txt", "w") as f:
                f.write(f"[{n.created_at}] Notification from {n.account.acct}, status {n.status.uri}\n")
                if link:
                    f.write(f"Indexed link: {link}")
                else:
                    f.write("No links found")


def run_forever():
    while True:
        print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Checking notifications...")
        old_notifications = glob.glob(".mastodon/*.txt")
        process_new_notifications()
        new_notifications = glob.glob(".mastodon/*.txt")
        diff = len(new_notifications) - len(old_notifications)
        print(f"\tprocessed {diff} notifications!")

        time.sleep(10)

if __name__ == "__main__":
    with app.app_context():
        run_forever()
