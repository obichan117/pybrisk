"""Margin lending (JSFC) models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class JSFCEntry(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    date: str
    sochi: str = ""
    kakuhoLongShares: int | None = None
    kakuhoShortShares: int | None = None
    sokuhoLongShares: int | None = None
    sokuhoShortShares: int | None = None
    standardizedLongShares: int | None = None
    standardizedShortShares: int | None = None
    gyakuhibuFee: float | None = None
    gyakuhibuFeePercent: float | None = None
    gyakuhibuFeeDayCount: int | None = None
    gyakuhibuMaxFee: float | None = None
