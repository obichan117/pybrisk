# BRiSK Authentication

## Session Flow

1. User logs into SBI Securities website (sbisec.co.jp)
2. Navigates to 全板/BRiSK service → opens `sbi.brisk.jp/#`
3. Session is cookie-based (HTTPOnly cookies, not visible in HAR)
4. All API calls authenticated via session cookies (`Vary: Cookie` on responses)

## Tokens

| Token | Source | Format | Purpose |
|---|---|---|---|
| `api_token` | `frontend/boot` | PASETO v2.local (~400 chars) | API authentication |
| `csrf_token` | `frontend/boot` | SHA-256 hex (64 chars) | CSRF protection |
| `tfx_token` | `frontend/boot` | PASETO v2.local (~300 chars) | TFX API auth |
| `market-token` | `app/market-token` | PASETO v2.local (~450 chars) | Real-time data / WebSocket auth |
| `data.token` | `frontend/boot` | MD5 hex (32 chars) | SBI Securities redirect |
| `identity` | `frontend/boot` | SHA-256 hex (64 chars) | User identity hash |
| `ws session` | `app/boot` ws_url | hex (~200 chars) | WebSocket connection auth |

## Token Format

All major tokens use **PASETO v2.local** (symmetric-key encrypted, not inspectable client-side).

## SBI Securities Redirect URL

`frontend/boot` returns a full redirect URL:
```
https://site0.sbisec.co.jp/marble/domestic/priceboard/full/complete.do?Param6=v2.local.{PASETO}&Param7={identity_hash}
```

## Two-Phase Auth Flow (Confirmed via Integration Testing)

1. `GET /api/frontend/boot` — authenticated by **session cookie only**
2. Response contains `api_token` (PASETO v2.local)
3. All subsequent requests require `Authorization: Bearer {api_token}` header
4. `GET /api/app/boot` — requires Bearer token (returns 401 without it)

The HAR didn't capture this because Chrome DevTools stripped the cookie headers, and the Authorization header was set by Angular after the first boot call.

## Key Notes

- `frontend/boot` = cookie-only auth → returns `api_token`
- All other endpoints = `Authorization: Bearer {api_token}` (from `frontend/boot`)
- Single-device limitation (one active session)
- `session_expires` field in `frontend/boot` provides session expiry as Unix timestamp
