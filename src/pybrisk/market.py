"""Market class — market-wide data access."""

from __future__ import annotations

import base64
import json
import zlib
from typing import TYPE_CHECKING, Any

import pandas as pd

if TYPE_CHECKING:
    from pybrisk._internal.client import Client


class Market:
    """Access market-wide data from BRiSK.

    Usage::

        market = Market(client=client)
        df = market.stocks_info()
        lists = market.stock_lists()
        df = market.alerts()
    """

    def __init__(self, *, client: Client) -> None:
        self._client = client

    def stocks_info(self) -> pd.DataFrame:
        """Fetch turnover and shares outstanding for all TSE stocks.

        Returns:
            DataFrame with ~3800 rows: code, turnover, shares_outstanding.
        """
        infos = self._client.fetch_stocks_info()
        rows = [
            {
                "code": i.issue_code,
                "turnover": i.turnover,
                "shares_outstanding": i.calc_shares_outstanding,
            }
            for i in infos
        ]
        return pd.DataFrame(rows)

    def stock_lists(self) -> dict[str, list[str]]:
        """Fetch curated stock lists (IPO, NK225, etc.).

        Returns:
            Dict mapping list_id to list of stock codes.
        """
        resp = self._client.fetch_stock_lists()
        return {sl.id: sl.issue_codes for sl in resp.stock_lists}

    def alerts(self, index_from: int = 0, index_to: int = 618) -> pd.DataFrame:
        """Fetch market condition alerts.

        Args:
            index_from: Start index for pagination.
            index_to: End index for pagination.

        Returns:
            DataFrame with market condition events.
        """
        conditions = self._client.fetch_markets(index_from=index_from, index_to=index_to)
        rows = [
            {
                "index": c.index,
                "code": c.issue_code,
                "kind": c.kind,
                "type": c.type,
                "price": c.price10 / 10.0 if c.price10 is not None else None,
                "value": c.value10 / 10.0 if c.value10 is not None else None,
                "diff_bps": c.diff_bps_from_last,
                "time": c.time,
            }
            for c in conditions
        ]
        return pd.DataFrame(rows)

    def schedule(self) -> dict[str, Any]:
        """Fetch trading session schedule.

        Returns:
            Dict with session times (nanoseconds from midnight JST) and status.
        """
        boot = self._client.app_boot
        info = boot.schedule_info
        return {
            "date": boot.date,
            "status": boot.session_status,
            "morning_pre_open": info.morning_session_pre_open_time,
            "morning_open": info.morning_session_open_time,
            "morning_close": info.morning_session_close_time,
            "afternoon_pre_open": info.afternoon_session_pre_open_time,
            "afternoon_open": info.afternoon_session_open_time,
            "afternoon_pre_close": info.afternoon_session_pre_close_time,
            "afternoon_close": info.afternoon_session_close_time,
        }

    def watchlist(self) -> list[str]:
        """Fetch user's saved watchlist stock codes.

        Returns:
            List of stock code strings.
        """
        resp = self._client.fetch_watchlist()
        if resp.empty:
            return []
        compressed = base64.b64decode(resp.data)
        decompressed = zlib.decompress(compressed)
        data = json.loads(decompressed)
        # Extract stock codes from watchlist structure
        codes: list[str] = []
        if isinstance(data, dict):
            for group in data.get("groups", []):
                for item in group.get("items", []):
                    if "code" in item:
                        codes.append(item["code"])
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, str):
                    codes.append(item)
                elif isinstance(item, dict) and "code" in item:
                    codes.append(item["code"])
        return codes
