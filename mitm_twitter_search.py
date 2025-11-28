"""
mitmproxy addon to intercept X/Twitter SearchTimeline GraphQL requests.

Usage:
  mitmdump -s mitm_twitter_search.py

This script will:
 - detect requests whose path looks like /i/api/graphql/<id>/SearchTimeline
 - log a short summary to mitmproxy's console
 - write a JSON-lines entry to `mitm_twitter_search_intercepts.jsonl` for every intercepted request+response

I'll keep this intentionally simple — we log content and save it for further processing or modification later.
"""

import re
import json
import time
from typing import Optional

from mitmproxy import ctx, http


SEARCH_ENDPOINT_RE = re.compile(r"^/i/api/graphql/[^/]+/SearchTimeline(?:\b|\?)")
OUTFILE = "mitm_twitter_search_intercepts.jsonl"
OUTFILE_EXTRACTED = "mitm_twitter_search_extracted.jsonl"


def _safe_decode(b: Optional[bytes]) -> Optional[str]:
	if b is None:
		return None
	try:
		return b.decode("utf-8")
	except Exception:
		try:
			return b.decode("latin-1")
		except Exception:
			return "<binary>"


class TwitterSearchInterceptor:
	"""A small mitmproxy addon to detect SearchTimeline GraphQL requests to x.com and log them.

	- When a request matches, we record request details, then mark the flow so the response is also saved.
	- Each intercept is appended to a JSONL file for post-processing.
	"""

	def __init__(self) -> None:
		self.outfile = OUTFILE
		self.outfile_extracted = OUTFILE_EXTRACTED

	def _record(self, data: dict) -> None:
		try:
			with open(self.outfile, "a", encoding="utf-8") as fh:
				fh.write(json.dumps(data, ensure_ascii=False) + "\n")
		except Exception as e:
			ctx.log.warn(f"Failed to write intercept to {self.outfile}: {e}")

	def _record_extracted(self, data: dict) -> None:
		"""Persist an extracted tweet object to the extracted JSONL file."""
		try:
			with open(self.outfile_extracted, "a", encoding="utf-8") as fh:
				fh.write(json.dumps(data, ensure_ascii=False) + "\n")
		except Exception as e:
			ctx.log.warn(f"Failed to write extracted tweet to {self.outfile_extracted}: {e}")

	def _find_first(self, obj, key):
		"""Recursively search for the first occurrence of key in nested dict/list structures."""
		if obj is None:
			return None
		if isinstance(obj, dict):
			if key in obj:
				return obj[key]
			for v in obj.values():
				res = self._find_first(v, key)
				if res is not None:
					return res
		elif isinstance(obj, list):
			for item in obj:
				res = self._find_first(item, key)
				if res is not None:
					return res
		return None

	def _is_tweet_candidate(self, obj: dict) -> bool:
		"""Heuristic: identify an object that likely represents a TimelineTweet."""
		if not isinstance(obj, dict):
			return False
		# common clues
		if obj.get("__typename") == "TimelineTweet":
			return True
		if "entryId" in obj and ("full_text" in obj or "id_str" in obj):
			return True
		# deeper legacy shapes
		if self._find_first(obj, "entryId") and self._find_first(obj, "full_text"):
			return True
		return False

	def _extract_timeline_tweets(self, parsed: dict) -> list:
		"""Extract TimelineTweet entries from the typical GraphQL response shape.

		We target: data.search_by_raw_query.search_timeline.timeline.instructions[*].entries[*]
		and look for entry.content.itemContent where itemType=="TimelineTweet" and
		tweet_results.result contains the tweet and nested user objects.
		"""
		found = []

		def _g(o, *path, default=None):
			"""Safe getter for nested dicts/lists using keys/indices.
			Example: _g(obj, 'data', 'search_by_raw_query', 'search_timeline')
			"""
			cur = o
			for p in path:
				if cur is None:
					return default
				if isinstance(cur, dict):
					cur = cur.get(p, None)
				elif isinstance(cur, list) and isinstance(p, int) and 0 <= p < len(cur):
					cur = cur[p]
				else:
					return default
			return cur

		entries = _g(parsed, "data", "search_by_raw_query", "search_timeline", "timeline", "instructions")
		if not entries:
			return found

		for instr in entries:
			en = instr.get("entries") if isinstance(instr, dict) else None
			if not en:
				continue
			for entry in en:
				try:
					entry_id = entry.get("entryId")
					content = entry.get("content", {})
					item = _g(content, "itemContent") or _g(content, "item_content")
					if not item:
						continue
					if item.get("itemType") != "TimelineTweet":
						# skip non-tweet things (cursors etc)
						continue

					tweet_res = _g(item, "tweet_results", "result") or {}
					user_res = _g(tweet_res, "core", "user_results", "result") or {}
					user_core = _g(user_res, "core") or {}
					user_legacy = _g(user_res, "legacy") or _g(user_core, "legacy") or {}
					tweet_core = _g(tweet_res, "core") or {}
					tweet_legacy = _g(tweet_core, "legacy") or {}

					obj = {
						"entryId": entry_id,
						"__typename": _g(item, "__typename") or _g(tweet_res, "__typename"),
						# user fields
						"name": _g(user_core, "name") or _g(user_res, "name"),
						"screen_name": _g(user_core, "screen_name"),
						"created_at": _g(user_core, "created_at"),
						"id": _g(user_res, "id") or _g(user_core, "id"),
						"is_blue_verified": _g(user_res, "is_blue_verified"),
						"location": _g(user_res, "location") or _g(user_core, "location"),
						"description": _g(user_legacy, "description") or _g(user_res, "profile_bio", "description"),
						"parody_commentary_fan_label": _g(user_res, "parody_commentary_fan_label"),
						"verified": _g(user_res, "verification", "verified") or _g(user_res, "verified"),
						# tweet fields
						"full_text": _g(tweet_legacy, "full_text"),
						"id_str": _g(tweet_legacy, "id_str") or _g(tweet_res, "rest_id"),
						"is_quote_status": _g(tweet_legacy, "is_quote_status"),
						"lang": _g(tweet_legacy, "lang"),
						"possibly_sensitive": _g(tweet_legacy, "possibly_sensitive"),
						"possibly_sensitive_editable": _g(tweet_legacy, "possibly_sensitive_editable"),
						"quote_count": _g(tweet_legacy, "quote_count"),
						"reply_count": _g(tweet_legacy, "reply_count"),
						"retweet_count": _g(tweet_legacy, "retweet_count"),
						"retweeted": _g(tweet_legacy, "retweeted"),
						"user_id_str": _g(tweet_legacy, "user_id_str") or _g(tweet_res, "core", "user_results", "result", "rest_id"),
					}

					# only include if at least one meaningful field exists
					if any(v is not None for k, v in obj.items() if k not in ("__typename",)):
						found.append(obj)

				except Exception as e:
					ctx.log.warn(f"Skipping entry while extracting: {e}")

		return found

	def request(self, flow: http.HTTPFlow) -> None:
		# Only consider https://x.com host with a SearchTimeline GraphQL path
		# Note: flows carry .request.host and .request.path
		try:
			host = flow.request.host or ""
			path = flow.request.path or ""
			if host.endswith("x.com") and SEARCH_ENDPOINT_RE.search(path):
				ctx.log.info(f"[SearchTimeline] request matched --> {flow.request.method} {flow.request.pretty_url}")

				req_body = _safe_decode(flow.request.raw_content)

				record = {
					"ts": time.time(),
					"event": "request",
					"method": flow.request.method,
					"url": flow.request.pretty_url,
					"host": host,
					"path": path,
					"headers": dict(flow.request.headers),
					"query": flow.request.query.fields if hasattr(flow.request, "query") else str(flow.request.query),
					"body": req_body,
				}

				# mark flow so response() will handle it too
				flow.metadata["twitter_search_intercept"] = True
				flow.metadata["twitter_search_record"] = record

				# persist request-only info now
				self._record(record)

		except Exception as e:
			ctx.log.error(f"Error in TwitterSearchInterceptor.request: {e}")

	def response(self, flow: http.HTTPFlow) -> None:
		try:
			if flow.metadata.get("twitter_search_intercept"):
				record = flow.metadata.get("twitter_search_record", {})
				resp_body = _safe_decode(flow.response.raw_content)

				record_resp = {
					"ts": time.time(),
					"event": "response",
					"url": flow.request.pretty_url,
					"status_code": flow.response.status_code,
					"reason": flow.response.reason,
					"headers": dict(flow.response.headers),
					"body": resp_body,
				}

				# Merge into one object for easier processing or write as separate entry
				combined = {"request": record, "response": record_resp}
				self._record(combined)

				# Attempt to extract a compact set of Tweet fields the user requested
				try:
					parsed = None
					# try to parse response body as JSON
					try:
						parsed = json.loads(resp_body) if isinstance(resp_body, str) else None
					except Exception:
						parsed = None

					if parsed is not None:
						tweets = self._extract_timeline_tweets(parsed)
						if tweets:
							# write each extracted tweet object as JSONL to a dedicated output file
							for t in tweets:
								self._record_extracted(t)

				except Exception as e:
					ctx.log.warn(f"Failed to extract tweets from response: {e}")

				ctx.log.info(f"[SearchTimeline] response saved --> {flow.request.pretty_url} {flow.response.status_code}")

		except Exception as e:
			ctx.log.error(f"Error in TwitterSearchInterceptor.response: {e}")


addons = [TwitterSearchInterceptor()]


