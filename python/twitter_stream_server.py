#!/usr/bin/env python

import json
import os
import sys
import time

from multiprocessing import Process, Value
from pprint import pprint

import tweetstream

import pusher

def track(total, username, password, *keywords):
    reconnect_wait = 5 # Wait 5 secs before reconnecting
    errors = 0
    
    print >> sys.stderr, "Tracking %s..." % ", ".join(keywords)
    while errors < 10:
        try:
            with tweetstream.FilterStream(username, password, track=keywords) as stream:
                for tweet in stream:
                    if "text" in tweet:
                        # print >> sys.stderr, tweet["text"]
                        total.value += 1
        
        except tweetstream.ConnectionError, e:
            print >> sys.stderr, e
            
            # Increment error count
            errors += 1
            
            # Wait before reconnecting
            time.sleep(reconnect_wait)
            
            # Back off gradually
            reconnect_wait *= 2

def main(config):
    # Prepare Pusher instance
    pusher.app_id = config["pusher"]["app_id"].encode("ascii")
    pusher.key = config["pusher"]["key"].encode("ascii")
    pusher.secret = config["pusher"]["secret"].encode("ascii")
    pusher_client = pusher.Pusher()
    
    # Shareable total between processes
    # See http://docs.python.org/library/multiprocessing.html#sharing-state-between-processes
    total = Value("d", 0.0)
    
    # Tweet handler, to receive/process tweets from stream
    # tweet_handler = TweetHandler(config)    
    process = Process(target=track, args=(total, config["twitter_auth"]["username"], config["twitter_auth"]["password"], config["search_terms"]))
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

if __name__ == "__main__":
    # Load config
    config_path = os.path.dirname(sys.argv[0]) + os.path.sep + "config.json"
    print >> sys.stderr, "Getting config from %s" % config_path
    config = json.load(open(config_path, "r"))
    main(config)
