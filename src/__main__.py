import logging
import sys
import time
from datetime import datetime
from queue import PriorityQueue

import tweepy
from apscheduler.schedulers.background import BackgroundScheduler

from src.selectors.greedy_selector import GreedySelector
from src.storagehandlers.json_storage_handler import JsonStorageHandler
from src.twitter.authentication import authenticate_1
from src.twitter.tweet_listener import TweetListener
from src.utils.config import Config


# this function will be called in intervals and will pop the top tweet from selected_tweets and retweet it
def retweet_function():
    global selected_tweets
    global api

    if selected_tweets.qsize() == 0:
        return
    (rate, status_id) = selected_tweets.get(block=False)
    logging.warning('retweeting message with rating(' + str(rate * -1) + '): ' + str(status_id))
    api.retweet(status_id)


def main():
    # globals
    global selected_tweets
    global api
    global config

    if not config.TRACKS:
        config.TRACKS = ['twitter']

    logging.warning('starting config:'
                    + '\nretweet interval: ' + str(config.RETWEET_INTERVAL)
                    + '\nsave_tweets: ' + str(config.SAVE_TWEETS)
                    + '\nsave_tweets_path: ' + config.SAVE_TWEETS_PATH
                    + '\ntracks: ' + " ".join(config.TRACKS))
    try:
        auth = authenticate_1(config.CONSUMER_KEY, config.CONSUMER_SECRET, config.TOKEN_KEY, config.TOKEN_SECRET)
        api = tweepy.API(auth)

        tweet_selector = GreedySelector(api, config.TRACKS)
        storage_handler = None
        if config.SAVE_TWEETS:
            storage_handler = JsonStorageHandler(config.SAVE_TWEETS_PATH)
        listener = TweetListener(selected_tweets, tweet_selector, storage_handler)
        stream = tweepy.Stream(auth=auth, listener=listener)
        # starting stream
        stream.filter(track=config.TRACKS, languages=["fa"])
    except Exception:
        logging.error("Unexpected error: " + str(sys.exc_info()))


if __name__ == "__main__":
    global config
    # load configs from file
    with open('../config.json', 'r', encoding="utf-8") as file:
        config = Config(file)

    selected_tweets = PriorityQueue()

    stream_scheduler = BackgroundScheduler()
    stream_scheduler.add_job(main,
                             trigger='interval',
                             minutes=30,
                             max_instances=1,
                             name='stream_scheduler',
                             next_run_time=datetime.now(),
                             id='stream_scheduler')
    stream_scheduler.start()

    # scheduler to call retweet_function in intervals
    retweet_scheduler = BackgroundScheduler()
    retweet_scheduler.add_job(retweet_function,
                              trigger='interval',
                              minutes=config.RETWEET_INTERVAL,
                              max_instances=1,
                              name='retweet_scheduler',
                              id='retweet_scheduler')
    retweet_scheduler.start()

    # apscheduler mostly used in web server application, it can't start a job when the main thread is terminated
    # so this infinit loop will keep the main thread running
    # todo: find a better way(suggestion: port hole bot to flask or django and create an gui as well)
    while True:
        time.sleep(10)

    # auth = authenticate_2(config.CONSUMER_KEY, config.CONSUMER_SECRET)
    # api = tweepy.API(auth)
    # for tweet in tweepy.Cursor(api.search, q='tweepy').items(10):
    #     print(tweet.text)
