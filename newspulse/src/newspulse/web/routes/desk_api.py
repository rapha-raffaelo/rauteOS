"""Versioned Desk contract. Only explicitly declared fields leave the ORM."""
from __future__ import annotations

import datetime as dt
from typing import Literal

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from ... import config, desk
from ..app import get_db

router = APIRouter(prefix="/api/v1", tags=["desk"])


class ReadModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ClientSummary(ReadModel):
    id: int
    name: str
    industry: str | None


class ActionCount(ReadModel):
    released: int
    logged: int
    total: int


class TwinSummary(ReadModel):
    percent: int
    profile_filled: int
    profile_total: int
    kickoff_settled: int
    kickoff_total: int
    has_guide: bool
    required_filled: int | None
    required_total: int | None
    gaps: list[str]


class MandateSummary(ReadModel):
    client: ClientSummary
    twin: TwinSummary
    actions_month: ActionCount
    actions_quarter: ActionCount
    promised_quarter: int | None
    opportunities: int
    status: Literal["krise", "aktiv", "ruhig"]
    on_track: bool | None


class DecisionSummary(ReadModel):
    client: ClientSummary
    kind: Literal["freigabe", "kundenfreigabe", "impuls", "profil"]
    title: str
    detail: str
    since: dt.datetime | None
    href: str


class InFlightSummary(ReadModel):
    client: ClientSummary
    title: str
    state: Literal["raus", "entwurf"]
    since: dt.datetime
    href: str


class DeskResponse(ReadModel):
    rows: list[MandateSummary]
    decisions: list[DecisionSummary]
    in_flight: list[InFlightSummary]
    generated_at: dt.datetime
    clients_active: int
    actions_month: int
    opportunities: int
    decisions_open: int
    twins_with_gaps: int
    twin_average: int
    timezone: str


@router.get("/desk", response_model=DeskResponse)
def read_desk(response: Response, session: Session = Depends(get_db)) -> DeskResponse:
    response.headers["Cache-Control"] = "no-store"
    board = desk.build(session)
    # No dataclasses.asdict(): a Client contains private notes and strategy.
    values = {name: getattr(board, name) for name in DeskResponse.model_fields if name != "timezone"}
    return DeskResponse.model_validate({**values, "timezone": str(config.local_zone())})
