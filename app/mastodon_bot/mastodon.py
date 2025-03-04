import os
import glob
import json
import time
import datetime

import bs4
from mastodon import Mastodon, StreamListener
from mastodon.errors import MastodonUnauthorizedError, MastodonNetworkError

from app import app
from app.utils_db import create_suggestion_in_db

if not os.path.isdir(".mastodon"):
    os.mkdir(".mastodon")

if app.config["MASTODON_API_TOKEN"]:
    # Create an instance of the Mastodon class
    mastodon = Mastodon(
        access_token=app.config["MASTODON_API_TOKEN"],
        api_base_url=app.config["MASTODON_INSTANCE"]
    )
else:
    mastodon = None


class PeARSBotStreamListener(StreamListener):
    def on_notification(self, n):
        if n.type == "mention" and n.status:
            link, info = process_mention(n.status, n.status.in_reply_to_id, "@" + n.account.acct)
            if link:
                print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] processed link {link}")
            print(f"\tinfo:{info}")


def process_new_notifications():

    for n in mastodon.notifications():
        # we only look at mentions
        if n.type != "mention":
            continue

        # only with linked statuses
        if not n.status:
            continue

        # ignore already processed mentions
        notification_id = n.id
        if os.path.isfile(f".mastodon/{n.id}.txt"):
            continue

        processed_link, info = process_mention(n.status, n.status.in_reply_to_id, "@" + n.account.acct)
        if processed_link:
            with open(f".mastodon/{n.id}.txt", "w") as f:
                f.write(f"[{n.created_at}] Notification from {n.account.acct}, status {n.status.uri}\n")
                f.write(f"Indexed link: {processed_link}")
                f.write(f"Info {info}")
        else:
            with open(f".mastodon/{n.id}.txt", "w") as f:
                f.write("No mention or no links found")
                f.write(f"Info {info}")


def process_mention(status, is_reply, user_handle, visibility="direct"):
    if "pearsbot-silent" in status.content:
        return None, "found 'pearsbot-silent', did nothing"

    if "pearsbot-suggest" in status.content:
        print(status.content)
        # first try to find a link in the message itself
        link = find_link_in_mention(status.content)

        # if we're replying to something and didn't find a link in the message itself
        if not link and is_reply:
            try:
                reply = mastodon.status(status.in_reply_to_id)
                soup = bs4.BeautifulSoup(reply.content, features="lxml")
                print(soup)
                links = soup.findAll("a")
                print(links)
                if not links:
                    link = None
                else:
                    links_not_hashtags_or_usernames = [l["href"] for l in links if not (l.text.startswith("#") or l.text.startswith("@"))]
                    if links_not_hashtags_or_usernames:
                        link = links_not_hashtags_or_usernames[-1]
                    else:
                        link = None
            except MastodonUnauthorizedError as e:
                link = None
                print(e.message)

        if link:
            create_suggestion_in_db(link, "mastodon-bot-suggestions", f"from {status.uri}", "mastodon-bot")
            mastodon.status_post(f"Beep beep, thanks for your suggestion, {user_handle}! I recorded the URL {link}. (Is this not what you intended? You can manually submit the correct URL instead - see link in bio.) The URL will be added to the index if the admins approve it, usually this happens within 48 hours.", in_reply_to_id=status.id, visibility=visibility)
        
        else:
            mastodon.status_post(f"Sorry {user_handle}, I couldn't find a link either in this post or in the post that you're replying to. You can try again by mentioning me and including \"pearsbot-suggest https://your-link-to-index.com\" OR by mentioning me when replying to a message that has a link in it. Alternatively, submit your URL manually or contact the admins - see link in bio.", in_reply_to_id=status.id, visibility=visibility)
        if link:
            return link, "found 'pearsbot-suggest', successfully processed link"
        else:
            return None, "found 'pearsbot-suggest', but couldn't find a link to process"
    
    mastodon.status_post(f"Hi {user_handle}, this is a friendly PeARS-bot. If you were trying to send a suggestion, something went wrong. Please include \"pearsbot-suggest\" in your message (see instructions in bio), or include \"pearsbot-silent\" if your message is meant for the (human!) admins and don't want an automated reply.", in_reply_to_id=status.id, visibility=visibility)

    return None, "no instructions found, sent default message"


def find_link_in_mention(mention_content, keyword="pearsbot-suggest"):
    soup = bs4.BeautifulSoup(mention_content, features="lxml")
    mention_paragraph = soup.find("p")
    mention_elements = list(mention_paragraph)
    keyword_position = -1
    for i, elem in enumerate(mention_elements):
        if keyword in elem.text:
            keyword_position = i
            break
    # check if there is a link right after the keyword location
    if keyword_position > -1:
        link_location = keyword_position + 1
        if link_location < len(mention_elements):
            if mention_elements[link_location].name == "a":
                return mention_elements[link_location]["href"]
        else:
            return None
    else:
        return None


def run_forever():
    start_time = time.time()
    # ideally, use the mastodon streaming API
    try:
        print(f"Listening for mentions of {app.config['MASTODON_USERNAME']} via the streaming API")
        mastodon.stream_user(PeARSBotStreamListener())
    # if it's not available, there's an alternative method
    except MastodonNetworkError as e:
        # only do the alternative if streaming fails right away
        if time.time() - start_time > 10:
            raise e
        print("Streaming API seems to be unavailable (for your instance and/or at this moment)")
        print("Trying to listen for notifications manually...")
        while True:
            print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Checking notifications...")
            old_notifications = glob.glob(".mastodon/*.txt")
            process_new_notifications()
            new_notifications = glob.glob(".mastodon/*.txt")
            diff = len(new_notifications) - len(old_notifications)
            print(f"\tprocessed {diff} notifications!")
            time.sleep(10)


def toot_new_page(url, title, theme, lang):
    post_text = (
        f"Beep beep, I just indexed a new page! 🤖\n"
        "\n"
        f"📰 Title: {title}\n"
        f"🍐 Theme: {theme}\n"
        f"💻 URL: {url}\n" 
        "\n"
        "[If you are the owner of this URL and don't like it being indexed, " 
        "please get in touch with us]"
    )
    
    post = mastodon.status_post(post_text)
    print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Tooted about new URL: {post.url}")

if __name__ == "__main__":
    with app.app_context():
        run_forever()
