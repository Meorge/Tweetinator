from os import access
import re
from time import sleep
import signal
import tweepy
from tweepy import api
import json
import csv
import os.path
from datetime import date, datetime, timedelta
import shortuuid
import random

from pymongo import MongoClient
from bson.objectid import ObjectId

import logging

from pathlib import Path

# Log into database
database_client = MongoClient()
tweet_db = database_client.tweetinator.tweets



abspath = os.path.abspath(__file__)
dname = os.path.abspath(os.path.join(os.path.dirname(abspath), "/bots"))

dname = os.path.join(Path(__file__).parents[1], 'bots')
print(f"abspath is {abspath}, dname is {dname}")
__default_date_string__ = "%d %b %Y %I:%M:%S %p"

logging.basicConfig(filename=os.path.join(os.path.dirname(abspath), "output.log"), level=logging.INFO, format='%(asctime)s --- %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')

class Bot:
    name = None
    consumer_key = None
    consumer_secret = None
    access_key = None
    access_secret = None

    def __init__(self, name):
        self.name = name

        config_json_filename = os.path.join(dname, f"{self.name}/config.json")

        assert os.path.exists(config_json_filename), f"{config_json_filename} does not exist!"

        try:
            config_json = open(config_json_filename, "r")
        except IOError:
            logging.exception(f"{self.name} - Couldn't open {config_json_filename}")
            return

        try:
            config = json.load(config_json)
        except json.decoder.JSONDecodeError as e:
            logging.exception(f"{self.name} - {config_json_filename} appears to be corrupted")
            return

        config_json.close()

        try:
            self.consumer_key = config["consumer_key"]
            self.consumer_secret = config["consumer_secret"]

            self.access_key = config["access_key"]
            self.access_secret = config["access_secret"]
        except KeyError:
            logging.exception(f"{self.name} - One or more keys in {config_json_filename} wasn't found")
            return


        # Now that the bot is ready to roll, let's make sure there are no tweets backed up
        # If there are, we'll send them to the archive
        try:
            unposted = self.get_unposted_items()
            now = datetime.now()
            backed_up = []
            for tweet in unposted:
                if datetime.fromisoformat(tweet["post_at"]) < now:
                    logging.info(f"{self.name} - tweet {tweet} was queued for before now, so sending it to the archive")
                    tweet["archive_reason"] = "Queued prematurely"
                    backed_up.append(tweet)

            unposted_without_backed_up = [ tweet for tweet in unposted if tweet not in backed_up ]

            self.write_unposted_items(unposted_without_backed_up)

            archived = self.get_archive_items()
            archived = self.sort_items(archived + backed_up, reverse=False)

            self.write_archive_items(archived)

        except Exception:
            logging.exception(f"{self.name} - Couldn't complete backlog cleaning")

    def get_auth(self):
        return tweepy.OAuthHandler(self.consumer_key, self.consumer_secret)

    def get_api(self):
        auth = self.get_auth()
        auth.set_access_token(self.access_key, self.access_secret)
        return tweepy.API(auth)

    @property
    def follower_counts_filename(self):
        return os.path.join(dname, f"{self.name}/followers.csv")

    @property
    def media_foldername(self):
        return os.path.join(dname, f"{self.name}/media")

    def get_item_from_id(self, id):
        print(f"looking for tweet with id {id}")
        id = ObjectId(id)
        return tweet_db.find_one(id)

    def archive_item(self, id, ripple=False):
        item_to_archive = self.get_item_from_id(id)

        # remove item from unposted
        items = self.get_unposted_items()
        items.reverse()

        if ripple:
            # Get index of item_to_archive
            index_to_archive = items.index(item_to_archive)

            

            start_index = index_to_archive

            # print(f"Ripple time! going from {start_index} to {0}")

            # For all subsequent items, move their dates down
            for i in range(0, start_index):
                # print(i)
                # print(items[i])
                # print(items[i+1])
                
                
                
                # Skip an item if it's set to not reschedule
                if items[i]["dont_reschedule"]: continue

                # print(f"{i} - \"{items[i]['text']}\" {items[i]['post_at']} should now be posted at \"{items[i+1]['text']}\" {items[i+1]['post_at']} time")
                # print("----")

                # this item should take the post_at date of
                # the item before it
                items[i]["post_at"] = items[i+1]["post_at"]



            # print("Done with ripple loop")


        items = [ item for item in items if item["id"] != item_to_archive["id"]]
        items.reverse()
        self.write_unposted_items(items)

        # print(f"Removing item {item_to_archive['text']} from queue")

        # add it to the archive
        archive = self.get_archive_items()
        archive.append(item_to_archive)
        self.write_archive_items(archive)

    def unarchive_item(self, id):
        result = tweet_db.update_one({"_id": ObjectId(id)}, {"$set": {"status": "unposted"}})
        return result

    def delete_item(self, id):
        result = tweet_db.delete_one({"_id": ObjectId(id)})
        return result

    def set_tweet(self, id, data):
        result = tweet_db.update_one({"_id": ObjectId(id)}, {"$set": data})
        return result

    def new_tweet(self, tweet=None):
        
        if tweet is None: tweet = {}

        if "text" not in tweet: tweet["text"] = ""
        if "dont_reschedule" not in tweet: tweet["dont_reschedule"] = False
        if "post_at" not in tweet: tweet["post_at"] = (datetime.now() + timedelta(days=1)).isoformat(timespec='seconds')
        if "media" not in tweet: tweet["media"] = ["", "", "", ""]
        if "id" not in tweet: tweet["id"] = shortuuid.uuid()
        if "reply_to" not in tweet: tweet["reply_to"] = ""

        # the mongoDB way
        tweet["bot_name"] = self.name
        tweet["status"] = "unposted"
        tweet["archive_reason"] = None

        return str(tweet_db.insert_one(tweet).inserted_id)

    def get_updated_tweet(self, old_tweet, new_tweet):
        if new_tweet["text"] is not None: old_tweet["text"] = new_tweet["text"]
        if new_tweet["dont_reschedule"] is not None: old_tweet["dont_reschedule"] = new_tweet["dont_reschedule"]
        if new_tweet["post_at"] is not None: old_tweet["post_at"] = new_tweet["post_at"]
        if new_tweet["media"] is not None: old_tweet["media"] = new_tweet["media"]
        if new_tweet["id"] is not None: old_tweet["id"] = new_tweet["id"]
        if new_tweet["reply_to"] is not None: old_tweet["reply_to"] = new_tweet["reply_to"]
        return old_tweet

    def write_follower_counts(self, data):
        with open(self.follower_counts_filename, "w") as f:
            csv_writer = csv.writer(f, delimiter=',')
            csv_writer.writerows(data)

    def get_follower_counts(self):
        if not os.path.exists(self.follower_counts_filename):
            logging.warning(f"{self.follower_counts_filename} doesn't exist, so returning an empty list")
            return []

        with open(self.follower_counts_filename, "r") as f:
            csv_reader = csv.reader(f, delimiter=',')
            return sorted([[datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S"), int(row[1])] for row in csv_reader], key= lambda i: i[0])

    def get_last_follower_count(self):
        follower_counts = self.get_follower_counts()

        previous_count = follower_counts[-1][1] if len(follower_counts) > 0 else 0

        new_follower_count = self.check_followers()

        if new_follower_count is not None and new_follower_count != previous_count:
            # there was a change in followers, so update the csv
            new_follower_entry = [datetime.now().strftime("%Y-%m-%d %H:%M:%S"), new_follower_count]
            follower_counts.append(new_follower_entry)
            self.write_follower_counts(follower_counts)

    def check_followers(self):
        api = self.get_api()
        try:
            follower_count = api.me().followers_count
        except tweepy.RateLimitError:
            logging.exception(f"{self.name} - rate limit error")
            follower_count = None
        except Exception:
            logging.exception(f"{self.name} - exception occurred trying to count followers")
            follower_count = None
        return follower_count

    def check_queue(self):
        # ok so we have the file
        unposted_items = self.get_unposted_items()

        # now we've got stuff to sort through
        new_unposted = unposted_items.copy()


        posted_this_time = []
        for item in unposted_items:
            # check the date on the item

            if item["post_at"] == "": continue
            
            item_post_date = datetime.fromisoformat(item["post_at"])
            if item_post_date < datetime.now():
                logging.info(f"{self.name} - Time to tweet: {json.dumps(item)}")
                updated_item = item.copy()
                updated_item["twitter_id"] = self.tweet_item(item)
                new_unposted.remove(item)
                
                if updated_item["twitter_id"] is None:
                    # it failed for some reason
                    # add it to the archive
                    updated_item["archive_reason"] = "Failed to post"
                    archive = self.get_archive_items()
                    archive.append(updated_item)
                    self.write_archive_items(archive)

                    # remove it from the queue
                    queue = self.get_unposted_items()
                    queue.remove(item)
                    self.write_unposted_items(queue)
                else:
                    posted_this_time.append(updated_item)

        # if nothing was posted, we don't have to do anything
        if len(posted_this_time) == 0: return
        # print(f"New unposted: {new_unposted}")

        # sort the unposted items
        new_unposted = self.sort_items(new_unposted)

        # update the unposted items file
        self.write_unposted_items(new_unposted)

        # update the posted items file

        posted_before = self.get_posted_items()
        posted_all = sorted(posted_before + posted_this_time, key = self.sort_by_date)

        self.write_posted_items(posted_all)

    def tweet_item(self, item):
        # Authenticate
        api = self.get_api()

        # Handle text
        text = item["text"] if "text" in item else ""

        # Handle media
        media_ids = []
        if "media" in item:
            media_paths = [os.path.join(self.media_foldername, image_name) for image_name in item["media"] if image_name != ""]

            # confirm all of these exist
            for path in media_paths:
                if not os.path.exists(path):
                    logging.error(f"{self.name} - path to media {path} could not be found")
                    return None

            try:
                media_ids = [api.media_upload(path).media_id_string for path in media_paths]
            except Exception:
                logging.exception(f"{self.name} - Error when trying to upload media")
                return None

        try:
            twitter_id = 0
            if "reply_to" in item:
                # First get the Tweetinator ID we want to reply to
                tweetinator_id = item["reply_to"]
                

                # Next, search through all posted items and find a Tweet with matching Tweetinator ID
                posted = self.get_posted_item_from_id(tweetinator_id)

                if posted is not None and 'twitter_id' in posted:
                    twitter_id = posted["twitter_id"]

            status: tweepy.Status = api.update_status(status=text, media_ids=media_ids, in_reply_to_status_id=int(twitter_id))
            return status.id
        except tweepy.TweepError:
            logging.exception(f"{self.name} - Error when trying to post Tweet")
            return None

    def get_upcoming_tweets(self, n=0):
        tweets = list(tweet_db.find({"bot_name": self.name, "status": "unposted"}).limit(n))
        return tweets

    def get_recent_tweets(self, n=0):
        tweets = list(tweet_db.find({"bot_name": self.name, "status": "posted"}).limit(n))
        return tweets

    def get_archive_tweets(self, n=0):
        tweets = list(tweet_db.find({"bot_name": self.name, "status": "archived"}).limit(n))
        return tweets

    def get_number_of_unposted_items(self):
        return tweet_db.count_documents({"bot_name": self.name, "status": "unposted"})

    def get_number_of_posted_items(self):
        return tweet_db.count_documents({"bot_name": self.name, "status": "posted"})

    def get_number_of_archived_items(self):
        return tweet_db.count_documents({"bot_name": self.name, "status": "archived"})

    def get_number_of_all_items(self):
        return (self.get_number_of_unposted_items(), self.get_number_of_posted_items(), self.get_number_of_archived_items())

    def redistribute_tweets(self, redistrib_info):
        try:
            initial_post_time = datetime.fromisoformat(redistrib_info["initialTime"])
            interval = int(redistrib_info["interval"])
            shuffle = redistrib_info["shuffle"]

            all_upcoming = self.get_unposted_items()

            all_upcoming_dont_reschedule = [ tweet for tweet in all_upcoming if tweet["dont_reschedule"] == True]
            all_upcoming_can_reschedule = [ tweet for tweet in all_upcoming if tweet["dont_reschedule"] == False]

            if shuffle:
                random.shuffle(all_upcoming_can_reschedule)

            # Let's set the dates!
            # Stat with initial date
            current_post_time = initial_post_time
            for tweet in all_upcoming_can_reschedule:
                tweet["post_at"] = current_post_time.isoformat(timespec='seconds')
                current_post_time += timedelta(minutes=interval)

            # Merge the two lists back together and sort
            all_upcoming_new = sorted(all_upcoming_dont_reschedule + all_upcoming_can_reschedule, key=self.sort_by_date)

            # Write these items to upcoming
            self.write_unposted_items(all_upcoming_new)
        except Exception as e:
            logging.exception(f"{self.name} - Error when redistributing tweets")
            return { "response": "failure", "message": f"{e}"}

        return { "repsonse": "success" }


