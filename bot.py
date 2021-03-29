from os import access
import re
from time import sleep
import signal
import pymongo
import tweepy
from tweepy import api
import json
import csv
import os.path
from datetime import date, datetime, timedelta, timezone
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

    initialized = False

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
            tweets_premature = tweet_db.update_many({"bot_name": self.name, "status": "unposted", "post_at": {"$lt": datetime.utcnow()}}, {"$set": {"status": "archived", "archive_reason": "Queued prematurely"}})
            logging.info(f"{self.name} - Archived {tweets_premature.modified_count} because they were queued for before now")
        except Exception:
            logging.exception(f"{self.name} - Couldn't complete backlog cleaning")

        self.initialized = True
        logging.info(f"{self.name} - initialization complete")

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
        try:
            return tweet_db.find_one(id)
        except Exception:
            logging.exception(f"{self.name} - couldn't find Tweet with id {id}")
            return None

    def archive_item(self, id, ripple=False):
        try:
            archive_result = tweet_db.update_one({"_id": ObjectId(id)}, {"$set": {"status": "archived", "archive_reason": "Manual"}})
            if ripple:
                start = tweet_db.find_one({"_id": ObjectId(id)}, {"_id": 0, "post_at": 1})["post_at"]

                # We want to move the items backwards
                items_to_move = list(tweet_db.find({"bot_name": self.name, "status": "unposted", "post_at": {"$gt": start}}).sort('post_at'))
                result = None
                for tup in enumerate(items_to_move):
                    i = tup[0]
                    item = tup[1]
                    if i == 0:
                        # first, so set this tweet's post at date to the one we archived
                        result = tweet_db.update_one({"_id": ObjectId(item['_id'])}, {"$set": {"post_at": start}})
                    else:
                        new_post_time = items_to_move[i-1]["post_at"]
                        result = tweet_db.update_one({"_id": ObjectId(item['_id'])}, {"$set": {"post_at": new_post_time}})

            return archive_result
        
        except Exception as e:
            logging.exception(f"{self.name} - Error archiving tweet")

    def unarchive_item(self, id):
        result = tweet_db.update_one({"_id": ObjectId(id)}, {"$set": {"status": "unposted"}})
        return result

    def delete_item(self, id):
        result = tweet_db.delete_one({"_id": ObjectId(id)})
        return result

    def set_tweet(self, id, data):
        if "post_at" in data and data["post_at"] is not None:
            data["post_at"] = datetime.fromisoformat(data["post_at"] + "+00:00")

        print(f"Received timestamp is {data['post_at'].isoformat(timespec='minutes')}")


        updates = {}
        if "text" in data: updates["text"] = data["text"]
        if "dont_reschedule" in data: updates["dont_reschedule"] = data["dont_reschedule"]
        if "post_at" in data: updates["post_at"] = data["post_at"]
        if "media" in data: updates["media"] = data["media"]
        if "reply_to" in data: updates["reply_to"] = data["reply_to"]

        result = tweet_db.update_one({"_id": ObjectId(id)}, {"$set": updates})
        return result

    def new_tweet(self, tweet=None):
        if tweet is None: tweet = {}

        print(f"Adding tweet - post_at is {tweet['post_at']}")

        tweet = {
            "text": tweet["text"] if "text" in tweet else "",
            "dont_reschedule": tweet["dont_reschedule"] if "dont_reschedule" in tweet else False,
            "post_at": datetime.fromisoformat(tweet["post_at"] + "+00:00") if "post_at" in tweet else (datetime.utcnow() + timedelta(days=1)),
            "media": tweet["media"] if "media" in tweet else ["", "", "", ""],
            "reply_to": tweet["reply_to"] if "reply_to" in tweet else "",
            "bot_name": self.name,
            "status": "unposted",
            "archive_reason": None,
            "twitter_id": None
        }

        return str(tweet_db.insert_one(tweet).inserted_id)

    def get_updated_tweet(self, old_tweet, new_tweet):
        if new_tweet["text"] is not None: old_tweet["text"] = new_tweet["text"]
        if new_tweet["dont_reschedule"] is not None: old_tweet["dont_reschedule"] = new_tweet["dont_reschedule"]
        if new_tweet["post_at"] is not None: old_tweet["post_at"] = new_tweet["post_at"]
        if new_tweet["media"] is not None: old_tweet["media"] = new_tweet["media"]
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
        if not self.initialized:
            logging.info(f"{self.name} - Initialization not finished, so returning")
            return

        try:
            unposted_items = tweet_db.find({"bot_name": self.name, "status": "unposted", "post_at": {"$lte": datetime.utcnow()}})
            for item in unposted_items:
                logging.info(f"{self.name} - Time to tweet: {item}")
                twitter_id = self.tweet_item(item)
                
                if twitter_id is None:
                    # it failed for some reason
                    # add it to the archive
                    tweet_db.update_one({"_id": ObjectId(item["_id"])}, {"$set": {"status": "archived", "archive_reason": "Failed to post"}})
                else:
                    tweet_db.update_one({"_id": ObjectId(item["_id"])}, {"$set": {"status": "posted", "twitter_id": twitter_id}})

        except Exception:
            logging.exception(f"{self.name} - error while checking queue")

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
            if "reply_to" in item and item["reply_to"] is not None and item["reply_to"] != "":
                # First get the Tweetinator ID we want to reply to
                tweetinator_id = item["reply_to"]
                

                # Next, search through all posted items and find a Tweet with matching Tweetinator ID
                posted = self.get_item_from_id(tweetinator_id)

                if posted is not None and 'twitter_id' in posted:
                    twitter_id = posted["twitter_id"]

            status: tweepy.Status = api.update_status(status=text, media_ids=media_ids, in_reply_to_status_id=int(twitter_id))
            return status.id
            
        except tweepy.TweepError:
            logging.exception(f"{self.name} - Error when trying to post Tweet")
            return None

    def get_upcoming_tweets(self, n=0):
        tweets = list(tweet_db.find({"bot_name": self.name, "status": "unposted"}).sort("post_at", pymongo.ASCENDING).limit(n))
        return tweets

    def get_recent_tweets(self, n=0):
        tweets = list(tweet_db.find({"bot_name": self.name, "status": "posted"}).sort("post_at", pymongo.ASCENDING).limit(n))
        return tweets

    def get_archive_tweets(self, n=0):
        tweets = list(tweet_db.find({"bot_name": self.name, "status": "archived"}).sort("post_at", pymongo.ASCENDING).limit(n))
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


            all_upcoming_can_reschedule = list(tweet_db.find({"bot_name": self.name, "dont_reschedule": False}))
            # Shuffle the rescheduleable ones if wanted
            if shuffle: random.shuffle(all_upcoming_can_reschedule)

            # Let's set the dates!
            # Stat with initial date
            current_post_time = initial_post_time
            for tweet in all_upcoming_can_reschedule:
                tweet_db.update_one({"_id": ObjectId(tweet["_id"])}, {"$set": {"post_at": current_post_time}})
                current_post_time += timedelta(minutes=interval)

        except Exception as e:
            print('FAILED TO REDISTRIBUTE')
            logging.exception(f"{self.name} - Error when redistributing tweets")
            return { "response": "failure", "message": f"{e}"}

        return { "repsonse": "success" }


