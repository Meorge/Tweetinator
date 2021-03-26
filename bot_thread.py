from os import wait
from threading import Thread, active_count
from time import sleep
from bot import Bot
from typing import Dict, List
from datetime import datetime

class BotThread(Thread):
    bots: Dict[str, Bot] = {}
    wait_duration: float = 10
    def __init__(self, wait_duration=10):
        super().__init__()
        self.wait_duration = wait_duration

    def add_bot(self, bot_name):
        self.bots[bot_name] = Bot(bot_name)

    def get_tweet(self, bot_name, tweet_id):
        return self.bots[bot_name].get_item_from_id(tweet_id)

    def archive_tweet(self, bot_name, tweet_id, ripple=False):
        return self.bots[bot_name].archive_item(tweet_id, ripple)

    def unarchive_tweet(self, bot_name, tweet_id):
        return self.bots[bot_name].unarchive_item(tweet_id)

    def delete_tweet(self, bot_name, tweet_id):
        return self.bots[bot_name].delete_item(tweet_id)

    def get_number_of_unposted_items(self, bot_name):
        return self.bots[bot_name].get_number_of_unposted_items()

    def get_number_of_posted_items(self, bot_name):
        return self.bots[bot_name].get_number_of_posted_items()

    def get_number_of_archived_items(self, bot_name):
        return self.bots[bot_name].get_number_of_archived_items()

    def get_number_of_all_items(self, bot_name):
        return self.bots[bot_name].get_number_of_all_items()

    def get_upcoming_tweets(self, bot_name, n=10, time_format="%d %b %Y %I:%M:%S %p"):
        return self.bots[bot_name].get_upcoming_tweets(n, time_format)

    def get_recent_tweets(self, bot_name, n=10, time_format="%d %b %Y %I:%M:%S %p"):
        return self.bots[bot_name].get_recent_tweets(n, time_format)

    def get_archive_tweets(self, bot_name, n=10, time_format="%d %b %Y %I:%M:%S %p"):
        return self.bots[bot_name].get_archive_tweets(n, time_format)

    def set_tweet(self, bot_name, tweet_id, tweet_data):
        return self.bots[bot_name].set_tweet(tweet_id, tweet_data)

    def new_tweet(self, bot_name, tweet_data=None):
        return self.bots[bot_name].new_tweet(tweet_data)

    def get_all_bots_info(self):
        list_of_bots = []
        for bot_name, bot in self.bots.items():
            list_of_bots.append((
                bot_name,
                self.get_number_of_unposted_items(bot_name),
                self.get_number_of_posted_items(bot_name),
                self.get_number_of_archived_items(bot_name)
            ))
        return list_of_bots

    def redistribute_tweets(self, bot_name, redistrib_info):
        return self.bots[bot_name].redistribute_tweets(redistrib_info)

    def run(self):
        while True:
            for bot_name, bot in self.bots.items():
                bot.check_queue()
            sleep(self.wait_duration)