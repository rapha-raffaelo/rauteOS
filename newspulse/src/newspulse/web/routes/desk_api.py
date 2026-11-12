"""Versioned Desk contract. Only explicitly declared fields leave the ORM."""
from __future__ import annotations

import datetime as dt
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from ... import config, desk, desk_brief, worklists
from ...analyzer import AnalyzerError
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
    has_guide: bool
    required_filled: int | None
    required_total: int | None
    gaps: list[str]
    parts: dict[str, dict[str, int]] = {}


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


class TaskSummary(ReadModel):
    id: int
    client: ClientSummary | None
    title: str
    priority: str
    status: str = "offen"
    due_on: dt.date | None
    href: str
    assignees: list[str] = []


class ChanceSummary(ReadModel):
    client: ClientSummary
    kind: Literal["detected", "developed"]
    title: str
    status: str
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
    chances: list[ChanceSummary] = []
    tasks: list[TaskSummary] = []
    tasks_open: int = 0
    tasks_due: int = 0
    #: Today's briefing in RAUTE's words, once somebody asked for it.
    briefing_ai: dict | None = None
    generated_at: dt.datetime
    clients_active: int
    actions_month: int
    opportunities: int
    decisions_open: int
    twins_with_gaps: int
    twin_average: int
    timezone: str


@router.get("/desk", response_model=DeskResponse)
def read_desk(request: Request, response: Response, session: Session = Depends(get_db)) -> DeskResponse:
    response.headers["Cache-Control"] = "no-store"
    member = worklists.member_for(request.scope.get("user_email")) or ""
    board = desk.build(session, member=member)
    # No dataclasses.asdict(): a Client contains private notes and strategy.
    values = {name: getattr(board, name) for name in DeskResponse.model_fields
              if name not in ("timezone", "briefing_ai")}
    return DeskResponse.model_validate({**values, "timezone": str(config.local_zone()),
                                        "briefing_ai": desk_brief.cached(key=_brief_key(member, board))})


@router.post("/desk/briefing")
def write_briefing(request: Request, response: Response, session: Session = Depends(get_db)) -> dict:
    """One model call that phrases today's briefing from the Desk's figures."""
    response.headers["Cache-Control"] = "no-store"
    try:
        member = worklists.member_for(request.scope.get("user_email")) or ""
        board = desk.build(session, member=member)
        return desk_brief.write(board, key=_brief_key(member, board))
    except AnalyzerError as exc:
        raise HTTPException(status_code=502, detail=f"Das Briefing konnte nicht formuliert werden: {exc}") from exc


def _brief_key(member, board):
    import hashlib
    return member + ':' + hashlib.sha256(desk_brief.facts(board).encode()).hexdigest()
