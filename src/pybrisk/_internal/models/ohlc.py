"""OHLC candle models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class OHLCBar5Min(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    date: str
    index: int
    diff: int = 0
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    turnover: int
    open_turnover: int | None = None


class OHLCBar1Day(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    date: str
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    turnover: int


class OHLCBar1Week(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    year: int
    week: int
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    turnover: int


class OHLCBar1Month(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    year: int
    month: int
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    turnover: int


class OHLCResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    ohlc5min: list[OHLCBar5Min] = []
    ohlc1day: list[OHLCBar1Day] = []
    ohlc1week: list[OHLCBar1Week] = []
    ohlc1month: list[OHLCBar1Month] = []
