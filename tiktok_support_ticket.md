# TikTok Support Ticket — Offline Events API accepting events but Events Manager shows 0

**Subject:** Offline Events API returning `code: 0` for 6 weeks of daily uploads, but Events Manager shows 0 total events on data source 7563436753504452626

Hi TikTok Support,

We have a daily offline conversions pipeline that has been sending events to the TikTok Events API v1.3 since **April 24, 2026**. Every daily run since then has completed successfully — each event receives an HTTP 200 with `code: 0`, `message: "OK"` — and we have ~3,000–4,000 events being acknowledged per day. However, the Events Manager dashboard for our offline data source shows **zero total events and a 0.00% match rate** for the entire time the pipeline has been live.

This is not a "wait 24 hours for processing" situation. We have over a month of accepted-but-invisible events. We need TikTok to confirm what is happening to these events after the API accepts them.

## Account / data source
- Business Center ID: `7233548874797891585`
- Ads account ID: `7233550720883048450`
- Offline Event Set ID (`event_source_id`): `7563436753504452626`
- Data source name: `offline`
- Data source created: 2025-10-20 15:52:29
- Status in Events Manager: Active

## Integration details
- Endpoint: `https://business-api.tiktok.com/open_api/v1.3/event/track/`
- Method: POST, JSON body, `Access-Token` header
- `event_source`: `offline`
- Event being sent: `Purchase`, mapped to standard event `Purchase` in Events Manager
- Identifiers per event: SHA-256 hashed `email` and `phone` (lowercase hex, phone normalized to E.164 without `+`)
- `event_id` per event: deterministic SHA-256 of `<order_id>|tiktok` (used for dedup; unique per order)
- Properties per event: `value` (float), `currency` ("USD"), `order_id`
- `test_event_code`: **not set** in production runs

## Evidence of successful sends from our side

The daily Cloud Run job (`social-capis-daily`) has been running since 2026-04-24 with no failures. Two representative executions:

**Run on 2026-05-30** (target business date 2026-05-29):
- Run start: `2026-05-30 15:01:16 UTC`
- Conversions fetched: 3,899
- Sent to TikTok: 3,899 ok / 0 errors
- All API responses: HTTP 200, `code: 0`, `message: "OK"`

**Run on 2026-06-02** (target business date 2026-06-01):
- Run start: `2026-06-02 15:02:17 UTC`
- Conversions fetched: 3,285
- Sent to TikTok: 3,285 ok / 0 errors
- All API responses: HTTP 200, `code: 0`, `message: "OK"`

Across roughly 40 daily runs since 2026-04-24 we have sent on the order of **120,000+ offline Purchase events**, all acknowledged by the API.

Manual probe sent today, also returning `code: 0`:
- Probe event_id: `tiktok-probe-1780401322`
- Sent: `2026-06-02 ~17:55 UTC`
- Response: `{"code": 0, "message": "OK", "request_id": "2026060217552206F8ED1C143C582B4646", "data": {}}`

## What Events Manager shows
For data source `7563436753504452626`, date range 2026-05-27 to 2026-06-02:
- Uploaded and matched events graph: "No events for the selected dates"
- Event type "Purchase" → Total events: 0, Matched events: 0, Match rate: 0.00%
- "Last recorded": 2026-06-02 08:00

This zero count is consistent across the entire 6-week history of the pipeline, not just the last 24 hours.

## What we need from TikTok
1. Confirm whether events for `event_source_id = 7563436753504452626` have actually been ingested on your side since 2026-04-24 — and if so, why they are not surfacing in Events Manager.
2. If events are being silently dropped after the API returns `code: 0`, what is the rejection reason? Examples we want ruled in or out:
   - `event_time` outside the acceptable window for offline conversions
   - Malformed identifier hashes (we hash lowercase email; phone normalized to E.164 digits-only before SHA-256)
   - Missing a required field for `event_source: offline` that the v1.3 spec does not flag at the API layer
   - Account-, business-, or data-source-level configuration (e.g., business verification, data sharing settings, regional restrictions) that suppresses surfaced events
3. Please trace the probe `event_id: tiktok-probe-1780401322` / `request_id: 2026060217552206F8ED1C143C582B4646` and confirm whether it reached the offline data source `7563436753504452626`.
4. Please pull a small sample of the `request_id`s ingested for this data source in the last 7 days and confirm the count matches the ~3,000–4,000/day we have sent.

Happy to provide additional `request_id`s, sanitized sample payloads, or read-only access to our Cloud Logging output on request.

Thanks,
Brent Christensen
bchristensen@cafezupas.com
