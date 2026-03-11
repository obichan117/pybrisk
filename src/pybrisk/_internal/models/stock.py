"""Stock info and stock list models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class StockInfo(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    issue_code: str
    turnover: int | None = None
    calc_shares_outstanding: int | None = None


class StockListEntry(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id: str
    name: str
    issue_codes: list[str]


class StockListsResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    version: str
    stock_lists: list[StockListEntry]
