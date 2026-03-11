"""Market condition models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class MarketCondition(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    index: int
    issue_code: str = ""
    kind: int | None = None
    type: int = 0
    price10: int | None = None
    value10: int | None = None
    diff_bps_from_last: int | None = None
    time: str = ""


class MarketsResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    market_conditions: list[MarketCondition]


class ScheduleInfo(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    morning_session_pre_open_time: int
    morning_session_open_time: int
    morning_session_close_time: int
    afternoon_session_pre_open_time: int
    afternoon_session_open_time: int
    afternoon_session_pre_close_time: int
    afternoon_session_close_time: int
    sq_jump_interval: int


class AppBootResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    result: bool
    series: int
    date: str
    session_status: str
    ws_url: str
    master: str
    snapshot: str
    time: int
    next_date: int
    schedule_info: ScheduleInfo


class FrontendBootResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    result: bool
    user_id: str
    identity: str
    csrf_token: str
    api_token: str
    api_endpoint: str
    session_expires: int
    tfx_token: str = ""
    tfx_api_base_url: str = ""


class WatchlistResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    empty: bool
    version: str = ""
    uuid: str = ""
    data: str = ""
