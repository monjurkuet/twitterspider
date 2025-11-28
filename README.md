## mitm_twitter_search

Small mitmproxy addon to intercept X/Twitter SearchTimeline GraphQL requests.

Features
- Detects requests with path like `/i/api/graphql/<id>/SearchTimeline` on hosts that end with `x.com`.
- Logs a short summary to mitmproxy's console.
- Appends request and response records to `mitm_twitter_search_intercepts.jsonl` (JSON Lines format).
- Extracts a compact set of Tweet fields (user + tweet fields) and appends them as JSON Lines to `mitm_twitter_search_extracted.jsonl`.

Usage (Windows / PowerShell)

1. Install mitmproxy:

```powershell
python -m pip install --upgrade pip
python -m pip install mitmproxy
```

2. Run mitmproxy headless (mitmdump) with the addon:

```powershell
mitmdump -s .\mitm_twitter_search.py
```

3. Use your browser or application with mitmproxy running (or configure your system to use the mitmproxy instance). Intercepted requests/responses will be logged and appended to `mitm_twitter_search_intercepts.jsonl`.

4. The addon now additionally parses SearchTimeline GraphQL responses for TimelineTweet items and will write a reduced JSON object containing only the fields you asked for to `mitm_twitter_search_extracted.jsonl`.

Example extracted fields written per tweet (one JSON object per line):

``json
{
	"name": "MemeContent | Viral Video Engine for Solana Memes",
	"screen_name": "memecontent_com",
	"created_at": "Sat Aug 07 07:35:20 +0000 2010",
	"id": "VXNlcjoxNzU2NzI2NTQ=",
	"is_blue_verified": true,
	"location": {"location": ""},
	"description": "MemeContent is building the meme-marketing — an AI-powered platform...",
	"parody_commentary_fan_label": "None",
	"verified": false,
	"entryId": "tweet-1994387910242734583",
	"__typename": "TimelineTweet",
	"full_text": "📈 BTC up 11.5% since Jim Cramer said ...",
	"id_str": "1994387910242734583",
	"is_quote_status": false,
	"lang": "en",
	"possibly_sensitive": false,
	"possibly_sensitive_editable": true,
	"quote_count": 0,
	"reply_count": 0,
	"retweet_count": 0,
	"retweeted": false,
	"user_id_str": "175672654"
}
```

Notes
- The script is intentionally focused on detection and logging. You can modify it to alter requests/responses (e.g., to inject headers or change payloads) — tell me what you'd like and I can extend it.
- Be mindful of legal and privacy implications when intercepting network traffic.

Next steps
- If you want, I can add filtering options, write unit tests, or provide helper scripts to parse `mitm_twitter_search_intercepts.jsonl`.
 - If you want, I can add filtering options, write unit tests, or provide helper scripts to parse the extracted file `mitm_twitter_search_extracted.jsonl`.

Local test runner
-----------------
If you want to validate the extraction logic without running mitmproxy, there's a small test helper under `test/run_extractor.py` and a trimmed sample response at `test/sample_search_response.json`.

Run it from the repo root (PowerShell):

```powershell
python .\test\run_extractor.py
```

The runner imports the addon class and calls the internal extractor on the sample response. This helps ensure the fields are pulled from the GraphQL shape: `data.search_by_raw_query.search_timeline.timeline.instructions[*].entries[*]`.
