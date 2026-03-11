# BRiSK Data Flow

## Request Sequence

```
Phase 1: Bootstrap (T+0ms)
  GET /api/frontend/boot
    → user_id, csrf_token, api_token, tfx_token, tfx_api_base_url

Phase 2: Parallel Init (T+62ms)
  GET /api/app/boot           → ws_url, master hash, snapshot hash, schedule
  GET /api/frontend/watchlist  → user's watchlist (compressed)
  POST tfx-api: ApiService/Boot → TFX master/snapshot hashes
  GET /api/master/{hash}       → master stock definitions
  GET /api/stocks_info         → turnover/outstanding for all stocks
  GET /api/stock_lists         → curated lists (IPO, NK225)

Phase 3: Market Data (T+508ms)
  GET /api/app/market-token    → PASETO token for real-time data
  GET /api/snapshot/{hash}     → full binary snapshot (29MB)
  GET tfx: /data/master/{hash} → futures definitions
  GET tfx: /data/snapshot/{hash} → futures prices

Phase 4: Events (T+708ms)
  GET /api/markets?index_from=0&index_to=618 → market condition events

Phase 5: WebSocket
  CONNECT wss://sbi.brisk.jp/realtime/0?session={token}
    → streaming real-time updates

Phase 6: User Interaction (on-demand)
  POST /api/stocks_update/0    → delta updates for viewed stocks
  GET /api/ohlc/{code}         → OHLC charts
  GET /api/jsfc/{code}         → margin lending data
```

## Dependency Graph

```
frontend/boot
  ├── tfx_token, tfx_api_base_url → TFX Boot → TFX master/snapshot hashes
  └── session cookies → all subsequent requests

app/boot
  ├── master hash → GET /api/master/{hash}
  ├── snapshot hash → GET /api/snapshot/{hash}
  └── ws_url → WebSocket connection

app/market-token → WebSocket auth (likely)
```

## Content-Addressable Storage

Master and snapshot URLs use SHA-256 hashes. Server returns hash via `app/boot`, client fetches exact version. Enables aggressive caching (`max-age=86400`).

## Encoding Conventions

- **Prices**: `price10` = price × 10 (integer, avoids floats)
- **Schedule times**: nanoseconds from midnight JST
- **Market event times**: microsecond-precision strings (`HH:MM:SS.μμμμμμ`)
- **Timestamps**: Unix seconds
- **Watchlist data**: zlib + base64
- **Tokens**: PASETO v2.local (encrypted, not inspectable)
