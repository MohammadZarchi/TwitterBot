import json
import logging
import threading
import time
from queue import Queue

import tweepy


class TweetListener(tweepy.StreamListener):
    def __init__(self, queue, selector, storage_handler=None):
        super().__init__()
        self.queue = queue
        self.selector = selector
        self.storage_handler = storage_handler
        self.fifo = Queue()
        self.executor = Executor(self.fifo, queue, selector, storage_handler)

    def on_status(self, status):
        self.fifo.put_nowait(status)

    def on_error(self, status_code):
        logging.warning('an error return by twitter, error code :' + str(status_code))

    def on_connect(self):
        self.executor.start()

    def on_disconnect(self, notice):
        logging.warning(notice)
        self.executor.killer = True
        self.executor.join()

    def on_exception(self, exception):
        logging.critical(exception)

    def on_limit(self, track):
        logging.warning('a limit message was return by twitter, ' + str(track))


class Executor(threading.Thread):
    def __init__(self, fifo, queue, selector, storage_handler):
        super().__init__()
        self.fifo = fifo
        self.queue = queue
        self.selector = selector
        self.storage_handler = storage_handler
        self.killer = False

    def run(self):
        while True:
            if self.fifo.qsize() == 0:
                if self.killer:
                    return
                time.sleep(5)
            else:
                self.handle_tweets()

    def handle_tweets(self):
        status = self.fifo.get()
        rating = self.selector.rate_tweet(status)  # get rating from selector
        if rating > 0.6:  # only add tweets with rating above 0.6
            # (-1 * rating) because python PQ uses min-heap(min value will pop first)
            self.queue.put((-1 * rating, status.id))
            with open('../temp_queue.json', 'w', encoding='utf-8') as queue_backup:
                json.dump(self.queue.queue, queue_backup)
        if self.storage_handler is not None:
            self.storage_handler.store_tweet(status)  # save tweets
