#!/usr/bin/env python

import json
import os
import sys
import signal
import time

from multiprocessing import Process, Value
from pprint import pprint
from threading import Timer

import tweepy
import tweepy_helpers

import pusher

class TweetHandler(object):
    tweets = None
    total = 0.0
    shared_total = None
    config = None
    
    def __init__(self, config):
        super(TweetHandler, self).__init__()
        self.tweets = []
        self.config = config    
    
    def __call__(self, tweet):
        # Keep the last 10000 tweets
        self.tweets.append(tweet)
        self.tweets = self.tweets[-10000:]
        
        self.total = self.total + 1.0
        self.shared_total.value = self.total
    
    def run(self, shared_total):
        print "Recording filter %s..." % self.config["search_terms"]
        self.shared_total = shared_total
        tweepy_helpers.stream("filter", self.config, self)
        

if __name__ == "__main__":
    # Load config
    config_path = os.path.dirname(sys.argv[0]) + os.path.sep + "config.json"
    print "Getting config from %s" % config_path
    config = json.load(open(config_path, "r"))
    
    # Prepare Pusher instance
    pusher.app_id = config["pusher"]["app_id"].encode("ascii")
    pusher.key = config["pusher"]["key"].encode("ascii")
    pusher.secret = config["pusher"]["secret"].encode("ascii")
    pusher_client = pusher.Pusher()
    
    # Shareable total between processes
    # See http://docs.python.org/library/multiprocessing.html#sharing-state-between-processes
    total = Value("d", 0.0)
    
    # Tweet handler, to receive/process tweets from stream
    tweet_handler = TweetHandler(config)    
    process = Process(target=tweet_handler.run, args=(total,))
    process.start()
    
    last_total = 0.0
    while True:
        try:
            if total.value > 0.0:
                # Send total to Pusher
                print "Sending", total.value - last_total, "tweets"
                pusher_client["my-channel"].trigger("my-event", {"count": total.value - last_total})
                
                # Update last_total
                last_total = total.value
            
            # Check again in 1 second's time
            time.sleep(1.0)
            
        except KeyboardInterrupt, e:
            # Excit gracefully
            process.terminate()
            sys.exit(0)
        
        except Exception, e:
            print e