"""API client — orchestrates session calls and parses into models."""

from __future__ import annotations

from pybrisk._internal.endpoints import (
    APP_BOOT,
    FRONTEND_BOOT,
    JSFC,
    MARKET_TOKEN,
    MARKETS,
    OHLC,
    STOCK_LISTS,
    STOCKS_INFO,
    WATCHLIST,
)
from pybrisk._internal.models import (
    AppBootResponse,
    FrontendBootResponse,
    JSFCEntry,
    MarketCondition,
    MarketsResponse,
    OHLCResponse,
    StockInfo,
    StockListsResponse,
    WatchlistResponse,
)
from pybrisk._internal.session import Session


class Client:
    """Typed API client. Calls session for HTTP, returns Pydantic models."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._frontend_boot: FrontendBootResponse | None = None
        self._app_boot: AppBootResponse | None = None
        self._booted = False

    def _ensure_booted(self) -> None:
        if self._booted:
            return
        # Step 1: frontend/boot (cookie auth only) → get api_token
        self._frontend_boot = FrontendBootResponse.model_validate(
            self._session.get(FRONTEND_BOOT.url())
        )
        # Step 2: set Bearer token for all subsequent requests
        self._session.api_token = self._frontend_boot.api_token
        # Step 3: app/boot (requires Bearer token)
        self._app_boot = AppBootResponse.model_validate(self._session.get(APP_BOOT.url()))
        self._booted = True

    @property
    def frontend_boot(self) -> FrontendBootResponse:
        self._ensure_booted()
        assert self._frontend_boot is not None
        return self._frontend_boot

    @property
    def app_boot(self) -> AppBootResponse:
        self._ensure_booted()
        assert self._app_boot is not None
        return self._app_boot

    def _today(self) -> str:
        return self.app_boot.date

    def fetch_ohlc(self, code: str) -> OHLCResponse:
        url = OHLC.url(code=code)
        data = self._session.get(url, params={"date": self._today()})
        return OHLCResponse.model_validate(data)

    def fetch_jsfc(self, code: str, count: int = 365) -> list[JSFCEntry]:
        url = JSFC.url(code=code)
        data = self._session.get(url, params={"count": count})
        return [JSFCEntry.model_validate(v) for v in data.values()]

    def fetch_stocks_info(self) -> list[StockInfo]:
        url = STOCKS_INFO.url()
        data = self._session.get(url, params={"date": self._today()})
        return [StockInfo.model_validate(item) for item in data]

    def fetch_stock_lists(self) -> StockListsResponse:
        url = STOCK_LISTS.url()
        data = self._session.get(url, params={"date": self._today()})
        return StockListsResponse.model_validate(data)

    def fetch_markets(
        self, index_from: int = 0, index_to: int = 618
    ) -> list[MarketCondition]:
        url = MARKETS.url()
        data = self._session.get(
            url,
            params={
                "date": self._today(),
                "series": self.app_boot.series,
                "index_from": index_from,
                "index_to": index_to,
            },
        )
        resp = MarketsResponse.model_validate(data)
        return resp.market_conditions

    def fetch_watchlist(self) -> WatchlistResponse:
        url = WATCHLIST.url()
        data = self._session.get(url)
        return WatchlistResponse.model_validate(data)

    def fetch_market_token(self) -> str:
        url = MARKET_TOKEN.url()
        data = self._session.get(url)
        return data["token"]
