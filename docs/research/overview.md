# BRiSK Research Overview

## What is BRiSK?

Browser-based real-time full order book viewer by ArGentumCode K.K. (HFT firm spin-off). White-labeled to multiple Japanese brokers. SBI instance at `sbi.brisk.jp`.

## Architecture

- **Frontend**: Angular SPA + RxJS
- **Backend**: Golang, C++, Python on GCP (Kubernetes)
- **Data**: WebSocket + proprietary binary compression (1/20 ratio)
- **Auth**: Cookie-based session from SBI Securities SSO
- **Tokens**: PASETO v2.local (encrypted)

## Markets Covered

- **TSE stocks**: Full order book for ALL listed securities
- **TFX futures**: Via separate gRPC-Connect API
- **NOT covered**: Forex, options, non-TSE exchanges

## Key Capabilities (data-only, no order placement in SBI version)

- Full depth order book (all price levels)
- Tick data with microsecond timestamps
- OHLC candles: 5min, daily, weekly, monthly
- Market condition alerts (basket orders, limit up/down, volume surges, etc.)
- Margin lending data (JSFC)
- Stock info (turnover, shares outstanding)
- Curated stock lists (IPO, Nikkei 225)
- Heatmap visualization

## Research Files

- [API Endpoints](./api-endpoints.md) — All discovered REST/WebSocket/gRPC endpoints
- [Authentication](./authentication.md) — Session flow, tokens, auth mechanism
- [Data Schemas](./data-schemas.md) — Response body structures for every endpoint
- [Data Flow](./data-flow.md) — Request sequence, dependencies, encoding conventions
