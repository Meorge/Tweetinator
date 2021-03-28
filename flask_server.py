#!/usr/bin/python3.7
import logging
from os import wait
import os.path
from types import TracebackType
from bot_thread import BotThread
from flask import Flask, render_template, request
import json
from threading import Timer
from traceback import print_tb

# make sure to run the command
# export FLASK_APP=flask_server.py
# before running



app = Flask(__name__)

app.jinja_env.auto_reload = True

bot_thread = BotThread(wait_duration=60)
bot_thread.daemon = True


with open('../bots.json', 'r') as f:
    loaded_bots = json.load(f)

    for i in loaded_bots:
        bot_thread.add_bot(i)

bot_thread.start()

abspath = os.path.abspath(__file__)
log_file = os.path.join(os.path.dirname(abspath), "output.log")

log = logging.getLogger('werkzeug')
log.setLevel(logging.WARNING)

if __name__ == "__main__":
    print("hoo")
    app.run(debug=False)

@app.route('/<bot_name>/upcoming')
def upcoming_tweets(bot_name):
    all_bot_data = bot_thread.get_all_bots_info()

    if bot_name in bot_thread.bots:
        tweets = bot_thread.get_upcoming_tweets(bot_name, n=9999, time_format="%B %d, %Y at %I:%M:%S %p")
        number_of_items = bot_thread.get_number_of_all_items(bot_name)
        return render_template("upcoming.html.j2", bot_name=bot_name, tweets=tweets, all_bot_data=all_bot_data)
    else:
        return f"No bot is registered with name {bot_name}"

@app.route('/api/<bot_name>/tweets/<tweet_id>/archive')
def archive_tweet(bot_name, tweet_id):
    print("Archive tweet!")

    do_ripple = (request.args.get("ripple") == "true")
    print(f"do ripple is {do_ripple}")

    bot_thread.archive_tweet(bot_name, tweet_id, do_ripple)
    return json.dumps(
        {
            "response": "success"
        }
    )

@app.route('/api/<bot_name>/tweets/<tweet_id>/unarchive')
def unarchive_tweet(bot_name, tweet_id):
    print("Unarchive tweet!")
    bot_thread.unarchive_tweet(bot_name, tweet_id)
    return json.dumps(
        {
            "response": "success"
        }
    )

@app.route('/api/<bot_name>/tweets/<tweet_id>/delete')
def delete_tweet(bot_name, tweet_id):
    print("Delete tweet forever!")
    bot_thread.delete_tweet(bot_name, tweet_id)
    return json.dumps(
        {
            "response": "success"
        }
    )

@app.route('/<bot_name>/posted')
def recent_tweets(bot_name):
    all_bot_data = bot_thread.get_all_bots_info()
    if bot_name in bot_thread.bots:
        tweets = bot_thread.get_recent_tweets(bot_name, n=9999, time_format="%B %d, %Y at %I:%M:%S %p")
        number_of_items = bot_thread.get_number_of_all_items(bot_name)
        return render_template("posted.html.j2", bot_name=bot_name, tweets=tweets, all_bot_data=all_bot_data)
    else:
        return f"No bot is registered with name {bot_name}"

@app.route('/<bot_name>/archive')
def archive_tweets(bot_name):
    all_bot_data = bot_thread.get_all_bots_info()
    if bot_name in bot_thread.bots:
        tweets = bot_thread.get_archive_tweets(bot_name, n=9999, time_format="%B %d, %Y at %I:%M:%S %p")
        number_of_items = bot_thread.get_number_of_all_items(bot_name)
        return render_template("archive.html.j2", bot_name=bot_name, tweets=tweets, all_bot_data=all_bot_data)
    else:
        return f"No bot is registered with name {bot_name}"


@app.route('/log')
def output_log():
    all_bot_data = bot_thread.get_all_bots_info()
    return render_template("output_log.html.j2", all_bot_data=all_bot_data)

@app.route('/<bot_name>/tweets/<tweet_id>/edit')
def edit_tweet(bot_name, tweet_id):
    this_tweet = bot_thread.get_tweet(bot_name, tweet_id)
    return render_template("edit_tweet.html.j2", bot_name=bot_name, this_tweet=this_tweet, all_bot_data=bot_thread.get_all_bots_info())

@app.route('/<bot_name>/redistribute')
def redistribute_tweets(bot_name):
    return render_template("redistrib_tweets.html.j2", bot_name=bot_name, all_bot_data=bot_thread.get_all_bots_info())

@app.route('/<bot_name>/batch_add')
def batch_add_tweets(bot_name):
    return render_template("batch_add_tweets.html.j2", bot_name=bot_name, all_bot_data=bot_thread.get_all_bots_info())

@app.route('/api/stats')
def api_get_tweet_stats():
    all_bot_data = bot_thread.get_all_bots_info()

    json_list = []
    for bot in all_bot_data:
        json_list.append({
            "name": bot[0],
            "unposted": bot[1],
            "posted": bot[2],
            "archived": bot[3]
        })
    
    return {"response": "success", "data": json_list}

@app.route('/api/<bot_name>/tweets/<tweet_id>/set', methods=['POST'])
def api_set_tweet(bot_name, tweet_id):
    print(request.content_type)
    data = request.json
    print(f"json is {data}")

    text = data["text"] if "text" in data else None
    dont_reschedule = data["dont_reschedule"] if "dont_reschedule" in data else None
    post_at = data["post_at"] if "post_at" in data else None
    media = data["media"] if "media" in data else None
    id = data["id"] if "id" in data else tweet_id
    reply_to = data["reply_to"] if "reply_to" in data else None

    update_data = {
        "text": text,
        "dont_reschedule": dont_reschedule,
        "post_at": post_at,
        "media": media,
        "id": id,
        "reply_to": reply_to
    }

    success = bot_thread.set_tweet(bot_name, tweet_id, update_data)

    return { "response": "success" if success else "failure", "tweet_id": id }

@app.route('/api/<bot_name>/new_tweet')
def api_new_tweet(bot_name):
    new_tweet_id = bot_thread.new_tweet(bot_name)

    return { "response": "success" if new_tweet_id is not None else "failure", "tweet_id": new_tweet_id }

@app.route('/api/<bot_name>/batch_add', methods=['POST'])
def api_batch_add_tweets(bot_name):
    data = request.json
    print(data)

    successfully_added = 0

    try:
        for tweet in data:
            added_tweet = bot_thread.new_tweet(bot_name, tweet)
            successfully_added += 1
            print(f"Tweet added: {added_tweet}")

        return { "response" : "success" }

    except Exception as e:
        print_tb(e.__traceback__)
        return { "response" : "failure", "message": f"Added {successfully_added} Tweets before encountering error: {e}"}

@app.route('/api/<bot_name>/redistribute', methods=['POST'])
def api_redistribute_tweets(bot_name):
    data = request.json
    print(data)

    return bot_thread.redistribute_tweets(bot_name, data)

@app.route('/api/log')
def api_output_log():

    try:
        reverse_log = request.args.get('reverse')
    except:
        reverse_log = False

    log_content = "Could not load log content"
    try:
        with open(log_file, 'r') as f:
            log_content = [line.strip() for line in f.readlines()]

            if reverse_log:
                log_content.reverse()

            log_content = "\n".join(log_content)
    except IOError as e:
        log_content = f"{e}"

    return log_content


@app.route('/')
def homepage():
    all_bot_data = bot_thread.get_all_bots_info()
    return render_template('index.html.j2', all_bot_data=all_bot_data)

