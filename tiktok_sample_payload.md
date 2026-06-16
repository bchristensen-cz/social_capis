# TikTok Events API — Sample Payload for Support

This is the exact request our daily pipeline (`src/platforms/tiktok.py`) sends to the
TikTok Events API. Identifiers below are hashed (SHA-256) as in production; the
`Access-Token` is redacted in this document — paste the live token before sending.

## Account / data source
- Business Center ID: `7233548874797891585`
- Ads account ID: `7233550720883048450`
- Data source ID (`event_source_id`): `7563436753504452626` (name: "offline", **type: CRM**)

---

## 1. What we are sending today (the request that returns 200 / `code: 0` but is dropped)

**Endpoint**
```
POST https://business-api.tiktok.com/open_api/v1.3/event/track/
```

**Headers**
```
Access-Token: <REDACTED — paste live token here>
Content-Type: application/json
```

**Body**
```json
{
  "event_source": "offline",
  "event_source_id": "7563436753504452626",
  "data": [
    {
      "event": "Purchase",
      "event_time": 1748617200,
      "event_id": "9f2c1e7a4b6d8c0e1f3a5b7c9d1e2f3a4b5c6d7e8f90a1b2c3d4e5f60718293a4",
      "user": {
        "email": "5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8",
        "phone": "6b3a55e0261b0304143f805a24924d0c1c44524821305f31d9277843b8a10f4e"
      },
      "properties": {
        "value": 24.95,
        "currency": "USD",
        "order_id": "BR-1029384756"
      }
    }
  ]
}
```

**Representative response we receive**
```json
{
  "code": 0,
  "message": "OK",
  "request_id": "2026060217552206F8ED1C143C582B4646",
  "data": {}
}
```

---

## 2. Proposed fix — same request with `event_source: "crm"`

Per the technical team's note, since `7563436753504452626` is a CRM data source, the only
change is the `event_source` value. Endpoint, headers, `event_source_id`, and the entire
`data` structure are identical.

```json
{
  "event_source": "crm",
  "event_source_id": "7563436753504452626",
  "data": [
    {
      "event": "Purchase",
      "event_time": 1748617200,
      "event_id": "9f2c1e7a4b6d8c0e1f3a5b7c9d1e2f3a4b5c6d7e8f90a1b2c3d4e5f60718293a4",
      "user": {
        "email": "5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8",
        "phone": "6b3a55e0261b0304143f805a24924d0c1c44524821305f31d9277843b8a10f4e"
      },
      "properties": {
        "value": 24.95,
        "currency": "USD",
        "order_id": "BR-1029384756"
      }
    }
  ]
}
```

---

## Notes for the TikTok team
- `event_time` is Unix epoch seconds (UTC) at order time.
- `event_id` is a deterministic SHA-256 of `<order_id>|tiktok`, unique per order, used for dedup.
- `user.email` is SHA-256 of the lowercased email; `user.phone` is SHA-256 of the
  E.164 number with the leading `+` stripped (digits only).
- `test_event_code` is **not** set on production runs.
- Real batches contain up to 1,000 events in the `data` array; one event is shown here.

## Open questions for TikTok
1. Confirming the fix: should we send `event_source: "crm"` against this existing data
   source, or do we need to create a separate Offline event source (new `event_source_id`)
   to land these as offline conversions?
2. Will switching to `event_source: "crm"` backfill / surface the ~120k events already
   accepted since 2026-04-24, or do those need to be re-sent?
