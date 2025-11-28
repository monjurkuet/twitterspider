"""Run the extraction logic on the sample_search_response.json file and print results.

This is a standalone helper for development/testing. It imports the TwitterSearchInterceptor class
from the addon and calls its _extract_timeline_tweets method.

Usage:
    python test/run_extractor.py
"""
import json
import os
import sys

# ensure repo root on PYTHONPATH so we can import the addon
ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from mitm_twitter_search import TwitterSearchInterceptor

SAMPLE = os.path.join(os.path.dirname(__file__), "sample_search_response.json")

with open(SAMPLE, 'r', encoding='utf-8') as fh:
    parsed = json.load(fh)

addon = TwitterSearchInterceptor()
extracted = addon._extract_timeline_tweets(parsed)
print(json.dumps(extracted, indent=2, ensure_ascii=False))
