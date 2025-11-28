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

from __future__ import annotations

import re
import json
import time
import sqlite3
from contextlib import closing
import os
from typing import Optional

try:
    from mitmproxy import ctx
except Exception:
    # Allow importing this module in environments without mitmproxy (tests, runners)
    class _DummyLog:
        def info(self, *a, **k):
            print("INFO:", *a)
        def warn(self, *a, **k):
            print("WARN:", *a)
        def error(self, *a, **k):
            print("ERROR:", *a)

    class _DummyCtx:
        log = _DummyLog()

    ctx = _DummyCtx()

from typing import TYPE_CHECKING

if TYPE_CHECKING:
	# type-only import so runtime doesn't require mitmproxy
	from mitmproxy import http  # pragma: no cover


SEARCH_ENDPOINT_RE = re.compile(r"^/i/api/graphql/[^/]+/SearchTimeline(?:\b|\?)")
OUTFILE = "mitm_twitter_search_intercepts.jsonl"
# NOTE: extracted data is persisted into sqlite only; no JSONL extracted file maintained
OUTFILE_DB = "mitm_twitter_search.db"


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
		# use script directory so files are written to the repo folder predictably
		base = os.path.dirname(__file__)
		self.outfile = os.path.join(base, OUTFILE)
		# no extracted JSONL produced any more; data is persisted to sqlite DB
		self.db_path = os.path.join(base, OUTFILE_DB)
		# ensure DB and tables exist
		try:
			self._ensure_db()
		except Exception as e:
			ctx.log.warn(f"Could not initialize DB {self.db_path}: {e}")

	def _record(self, data: dict) -> None:
		try:
			with open(self.outfile, "a", encoding="utf-8") as fh:
				fh.write(json.dumps(data, ensure_ascii=False) + "\n")
		except Exception as e:
			ctx.log.warn(f"Failed to write intercept to {self.outfile}: {e}")

	def _ensure_db(self) -> None:
		"""Create sqlite DB and table if needed."""
		with closing(sqlite3.connect(self.db_path)) as conn:
			cur = conn.cursor()
			# Simple table creation — id_str is the single PRIMARY KEY. No migration logic.
			cur.execute(
				"""
				CREATE TABLE IF NOT EXISTS tweets (
					id_str TEXT PRIMARY KEY,
					entryId TEXT,
					typename TEXT,
					name TEXT,
					screen_name TEXT,
					created_at TEXT,
					user_base64_id TEXT,
					is_blue_verified INTEGER,
					location TEXT,
					description TEXT,
					parody_commentary_fan_label TEXT,
					verified INTEGER,
					full_text TEXT,
					is_quote_status INTEGER,
					lang TEXT,
					possibly_sensitive INTEGER,
					possibly_sensitive_editable INTEGER,
					quote_count INTEGER,
					reply_count INTEGER,
					retweet_count INTEGER,
					retweeted INTEGER,
					user_id_str TEXT,
					ts REAL
				)
				"""
			)
			conn.commit()
			ctx.log.info(f"Initialized DB at {self.db_path}")

	def _insert_extracted_db(self, data: dict) -> None:
		"""Insert the extracted tweet object into the sqlite DB."""
		# map booleans to 1/0 for sqlite
		def _to_int(val):
			if val is None:
				return None
			if isinstance(val, bool):
				return 1 if val else 0
			try:
				return int(val)
			except Exception:
				return None

		# choose id_str primary key only — require presence
		pk = data.get("id_str")
		if pk is None:
			# if we still don't have a primary key, skip storing — we don't want NULL primary keys
			ctx.log.warn("Skipping insert: no id_str/user_id_str/id/entryId available to use as primary key")
			return

		params = (
			pk,
			data.get("entryId"),
			data.get("__typename"),
			data.get("name"),
			data.get("screen_name"),
			data.get("created_at"),
			data.get("id"),
			_to_int(data.get("is_blue_verified")),
			json.dumps(data.get("location"), ensure_ascii=False) if data.get("location") is not None else None,
			data.get("description"),
			data.get("parody_commentary_fan_label"),
			_to_int(data.get("verified")),
			data.get("full_text"),
			_to_int(data.get("is_quote_status")),
			data.get("lang"),
			_to_int(data.get("possibly_sensitive")),
			_to_int(data.get("possibly_sensitive_editable")),
			_to_int(data.get("quote_count")),
			_to_int(data.get("reply_count")),
			_to_int(data.get("retweet_count")),
			_to_int(data.get("retweeted")),
			data.get("user_id_str"),
			time.time(),
		)

		try:
			with closing(sqlite3.connect(self.db_path)) as conn:
				cur = conn.cursor()
				changes_before = conn.total_changes
				cur.execute(
					"""
					INSERT OR IGNORE INTO tweets (
						id_str, entryId, typename, name, screen_name, created_at, user_base64_id,
						is_blue_verified, location, description, parody_commentary_fan_label,
						verified, full_text, is_quote_status, lang,
						possibly_sensitive, possibly_sensitive_editable, quote_count, reply_count,
						retweet_count, retweeted, user_id_str, ts
					) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
					""",
					params,
				)
				conn.commit()
				changes_after = conn.total_changes
				if changes_after > changes_before:
					ctx.log.info(f"Inserted tweet id_str={pk} into DB {self.db_path}")
				else:
					ctx.log.info(f"Ignored duplicate/no-op for id_str={pk} (DB: {self.db_path})")
		except Exception as e:
			ctx.log.warn(f"Failed to insert extracted tweet into DB {self.db_path}: {e}")

	def _record_extracted(self, data: dict) -> None:
		"""Persist an extracted tweet to the sqlite DB (replaces file-based writer)."""
		try:
			self._insert_extracted_db(data)
		except Exception as e:
			ctx.log.warn(f"Failed to persist extracted tweet to DB: {e}")

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
				# Prefer mitmproxy's decoded text when available (handles compressed content)
				resp_body = None
				try:
					if hasattr(flow.response, "get_text"):
						# mitmproxy provides get_text which handles decoding
						resp_body = flow.response.get_text(strict=False)
					elif hasattr(flow.response, "text"):
						resp_body = flow.response.text
				except Exception:
					resp_body = None

				if resp_body is None:
					# fallback to safe decode of raw_content
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
							# persist each extracted tweet into the sqlite DB
							for t in tweets:
								self._record_extracted(t)

				except Exception as e:
					ctx.log.warn(f"Failed to extract tweets from response: {e}")

				ctx.log.info(f"[SearchTimeline] response saved --> {flow.request.pretty_url} {flow.response.status_code}")

		except Exception as e:
			ctx.log.error(f"Error in TwitterSearchInterceptor.response: {e}")


addons = [TwitterSearchInterceptor()]


