"""The pages of spec 10: Aufgaben, LinkedIn and Sales CRM.

Plain forms that post and redirect back, like the archive and settings pages.
A value that cannot be stored re-renders the page with the reason and the
typed fields kept, rather than redirecting it away.
"""

from __future__ import annotations

import logging
import secrets
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from sqlalchemy.orm import Session

from ... import config, desk, linkedin_link, worklists, workspaces
from ...models import DEAL_STAGES, POST_STATES, TASK_PRIORITIES, TASK_STATES, Asset, Deal, LinkedInPost, Task, TaskBoard, TaskSubtask
from .. import redirects
from ..app import get_db
from ..react_pages import render as render_react

router = APIRouter()
_log = logging.getLogger(__name__)
_SEE_OTHER = 303
_LINKEDIN_STATE_COOKIE = "newspulse_linkedin_state"


def _clients(session: Session) -> list[dict]:
    return [dict(id=c.id, name=c.name) for c in worklists.mandates(session)]


def _subtasks(task):
    return [dict(id=row.id, title=row.title, completed=row.completed) for row in task.subtasks]


def _task(t: Task) -> dict:
    return dict(id=t.id, title=t.title, note=t.note, priority=t.priority, favorite=t.favorite, status=t.status,
                board_id=t.board_id, source_key=t.source_key, source_kind=t.source_kind, source_open=t.source_open,
                due_on=t.due_on, owner=t.owner, context_href=t.context_href, assignees=list(t.assignees or []),
                client=dict(id=t.client.id, name=t.client.name) if t.client else None,
                created_at=t.created_at, done_at=t.done_at, archived=worklists.task_archived(t), subtasks=_subtasks(t))


def _post(session: Session, p: LinkedInPost) -> dict:
    return dict(id=p.id, title=p.title, author=p.author, body=p.body, status=p.status,
                planned_on=p.planned_on, published_url=p.published_url,
                client=dict(id=p.client.id, name=p.client.name), updated_at=p.updated_at,
                source_href=_source_href(session, p), post_at=p.post_at, post_as=p.post_as,
                on_linkedin=bool(p.linkedin_urn), post_error=p.post_error)


def _source_href(session: Session, p: LinkedInPost) -> str:
    """Where the card came from: the chance, or the text RauteOS wrote."""
    if p.context_href:
        return p.context_href
    return workspaces.text_href(session, p.asset) if p.asset_id and p.asset else ""


def _deal(d: Deal) -> dict:
    return dict(id=d.id, company=d.company, contact_name=d.contact_name, contact_email=d.contact_email,
                stage=d.stage, value_eur=d.value_eur, owner=d.owner, next_step=d.next_step,
                next_step_on=d.next_step_on, note=d.note, closed_at=d.closed_at)


def _row_or_404(session: Session, model, row_id: int):
    row = session.get(model, row_id) if 0 < row_id < 2**62 else None
    if row is None:
        raise HTTPException(status_code=404, detail="Not found")
    return row


async def _form(request: Request) -> dict:
    """The posted fields; ``assignees`` keeps every ticked person, not the last."""
    form = await request.form()
    values = {k: v for k, v in form.items()}
    if "assignees" in form:
        values["assignees"] = form.getlist("assignees")
    return values


def _task_back(form: dict, fallback: str = "/aufgaben") -> str:
    """Where a task form returns: the list it was sent from, on this site only."""
    return redirects.local_target(str(form.pop("redirect_to", "") or ""), fallback)


# --- Aufgaben -------------------------------------------------------------------


def _tasks_page(request: Request, session: Session, *, error: str = "", draft: dict | None = None) -> Response:
    status = request.query_params.get("status", "")
    status = status if status in TASK_STATES else ""
    raw = request.query_params.get("client", "")
    client_id = int(raw) if raw.isdigit() else None
    boards = worklists.task_boards(session)
    worklists.sync_decision_tasks(session, desk.open_decisions(session, hide_settled=False), boards)
    rows = worklists.tasks(session, status=status, client_id=client_id, include_archived=True)
    everything = worklists.open_tasks(session)
    me = worklists.member_for(request.scope.get("user_email"))
    raw_board = request.query_params.get("board", "")
    selected_board = next((b for b in boards if str(b.id) == raw_board), None)
    if not raw_board:
        raw_task = request.query_params.get("aufgabe", "")
        task = next((row for row in rows if str(row.id) == raw_task), None)
        if task:
            selected_board = next((b for b in boards if b.id == task.board_id), None)
    selected_board = selected_board or next(b for b in boards if b.system_key == worklists.DEFAULT_BOARD)
    return render_react(request, "tasks", dict(
        tasks=[_task(t) for t in rows], clients=_clients(session), decisions=[],
        boards=[dict(id=b.id, name=b.name, system_key=b.system_key,
                     open_count=sum(t.board_id == b.id for t in everything)) for b in boards],
        active_board_id=None if raw_board == "all" else selected_board.id,
        default_board_id=next(b.id for b in boards if b.system_key == worklists.DEFAULT_BOARD),
        team=[dict(key=key, name=name) for key, name, _ in worklists.TEAM], me=me,
        open_total=len(everything), due_on=[t.due_on for t in everything if t.due_on],
        priorities=[[p, worklists.TASK_PRIORITY_LABELS[p]] for p in TASK_PRIORITIES],
        states=[[s, worklists.TASK_STATE_LABELS[s]] for s in TASK_STATES],
        filter=dict(status=status, client=client_id), error=error, draft=draft or {}))


@router.get("/aufgaben")
def tasks_view(request: Request, session: Session = Depends(get_db)) -> Response:
    if not request.query_params.get("board"):
        boards = worklists.task_boards(session)
        workspace = request.query_params.get("workspace")
        board = next((b for b in boards if workspace and b.system_key == workspace), None)
        raw_task = request.query_params.get("aufgabe", "")
        if board is None and raw_task.isdigit() and len(raw_task) < 19:
            task = session.get(Task, int(raw_task))
            if task:
                board = next((b for b in boards if b.id == task.board_id), None)
        board = board or next(b for b in boards if b.system_key == worklists.DEFAULT_BOARD)
        session.commit()
        query = dict(request.query_params)
        query.pop("workspace", None)
        query["board"] = str(board.id)
        return RedirectResponse("/aufgaben?" + urlencode(query), status_code=_SEE_OTHER)
    return _tasks_page(request, session)


@router.post("/aufgaben")
async def create_task(request: Request, session: Session = Depends(get_db)) -> Response:
    form = await _form(request)
    back = _task_back(form)
    try:
        worklists.save_task(session, form)
    except worklists.Invalid as exc:
        session.rollback()
        return _tasks_page(request, session, error=str(exc), draft=form)
    return RedirectResponse(back, status_code=_SEE_OTHER)


@router.post("/aufgaben/boards")
async def create_task_board(request: Request, session: Session = Depends(get_db)) -> Response:
    form = await _form(request)
    try:
        board = worklists.create_task_board(session, form)
    except worklists.Invalid as exc:
        session.rollback()
        return _tasks_page(request, session, error=str(exc), draft=form)
    return RedirectResponse(f"/aufgaben?board={board.id}", status_code=_SEE_OTHER)


@router.post("/aufgaben/{task_id}")
async def update_task(task_id: int, request: Request, session: Session = Depends(get_db)) -> Response:
    task = _row_or_404(session, Task, task_id)
    form = await _form(request)
    back = _task_back(form)
    try:
        if form and set(form) <= worklists.QUICK_FIELDS:  # ticking off, the star
            worklists.quick_update(session, task, form)
        else:
            worklists.save_task(session, form, task)
    except worklists.Invalid as exc:
        session.rollback()
        if "application/json" in request.headers.get("accept", ""):
            return JSONResponse({"error": str(exc)}, status_code=422)
        return _tasks_page(request, session, error=str(exc))
    if "application/json" in request.headers.get("accept", ""):
        return JSONResponse({"id": task.id, "status": task.status})
    return RedirectResponse(back, status_code=_SEE_OTHER)


@router.post("/aufgaben/{task_id}/delete")
async def delete_task(task_id: int, request: Request, session: Session = Depends(get_db)) -> Response:
    back = _task_back(await _form(request))
    task = _row_or_404(session, Task, task_id)
    if task.source_key:
        session.merge(worklists.DismissedTaskSource(source_key=task.source_key))
    session.delete(task)
    session.commit()
    return RedirectResponse(back, status_code=_SEE_OTHER)


@router.post("/aufgaben/{task_id}/subtasks")
async def create_subtask(task_id: int, request: Request, session: Session = Depends(get_db)):
    task = _row_or_404(session, Task, task_id)
    form = await _form(request)
    title = str(form.get("title", "")).strip()
    if not title or len(title) > 200:
        return JSONResponse({"error":"Bitte einen Titel mit 1 bis 200 Zeichen eingeben"}, status_code=422)
    task.subtasks.append(TaskSubtask(title=title))
    session.commit()
    return JSONResponse({"subtasks":_subtasks(task)})


@router.post("/aufgaben/{task_id}/subtasks/{subtask_id}")
async def update_subtask(task_id: int, subtask_id: int, request: Request, session: Session = Depends(get_db)):
    task = _row_or_404(session, Task, task_id)
    row = next((row for row in task.subtasks if row.id == subtask_id), None)
    if row is None:
        raise HTTPException(status_code=404, detail="Unteraufgabe nicht gefunden")
    form = await _form(request)
    if form.get("delete") == "1":
        task.subtasks.remove(row)
    else:
        if "title" in form:
            title = str(form["title"]).strip()
            if not title or len(title) > 200:
                return JSONResponse({"error":"Bitte einen Titel mit 1 bis 200 Zeichen eingeben"}, status_code=422)
            row.title = title
        if "completed" in form:
            if form["completed"] not in {"0", "1"}:
                return JSONResponse({"error":"Ungültiger Status"}, status_code=422)
            row.completed = form["completed"] == "1"
    session.commit()
    return JSONResponse({"subtasks":_subtasks(task)})


# --- LinkedIn -------------------------------------------------------------------


def _owner(request: Request) -> str:
    """Whose LinkedIn account: the RauteOS sign-in address (empty under basic auth)."""
    return request.scope.get("user_email", "")


def _account(request: Request) -> dict:
    found = linkedin_link.connection(_owner(request))
    return dict(configured=config.linkedin_configured(), connected=bool(found and found.usable()),
                name=found.name if found else "", expires_at=found.expires_at if found else None,
                expiring=bool(found and found.expiring()), lost=found.lost if found else "",
                expired=bool(found and not found.lost and not found.usable()))


def _posts_page(request: Request, session: Session, *, error: str = "", draft: dict | None = None,
                notice: str = "") -> Response:
    rows = worklists.posts(session)
    notice = notice or _LINKEDIN_NOTICES.get(request.query_params.get("konto", ""), "")
    return render_react(request, "linkedin", dict(
        posts=[_post(session, p) for p in rows], clients=_clients(session),
        states=[[s, worklists.POST_STATE_LABELS[s]] for s in POST_STATES],
        suggestions=worklists.suggestions(session), account=_account(request),
        error=error, notice=notice, draft=draft or {}))


@router.get("/linkedin")
def posts_view(request: Request, session: Session = Depends(get_db)) -> Response:
    return _posts_page(request, session)


@router.post("/linkedin")
async def create_post(request: Request, session: Session = Depends(get_db)) -> Response:
    form = await _form(request)
    try:
        worklists.save_post(session, form)
    except worklists.Invalid as exc:
        session.rollback()
        return _posts_page(request, session, error=str(exc), draft=form)
    return RedirectResponse("/linkedin", status_code=_SEE_OTHER)


@router.post("/linkedin/from-text/{asset_id}")
def post_from_text(asset_id: int, session: Session = Depends(get_db)) -> Response:
    asset = _row_or_404(session, Asset, asset_id)
    if asset.kind != "linkedin":
        raise HTTPException(status_code=404, detail="Not found")
    post = worklists.post_from_asset(session, asset)
    return RedirectResponse(f"/linkedin#post-{post.id}", status_code=_SEE_OTHER)


@router.post("/linkedin/from-chance")
async def post_from_chance(request: Request, session: Session = Depends(get_db)) -> Response:
    try:
        post = worklists.post_from_chance(session, await _form(request))
    except worklists.Invalid as exc:
        session.rollback()
        return _posts_page(request, session, error=str(exc))
    return RedirectResponse(f"/linkedin#post-{post.id}", status_code=_SEE_OTHER)


# --- The person's own LinkedIn account -------------------------------------------

_LINKEDIN_NOTICES = {
    "verbunden": "LinkedIn ist verbunden.",
    "getrennt": "LinkedIn ist getrennt.",
    "abgebrochen": "Die Anmeldung bei LinkedIn wurde abgebrochen.",
    "fehler": "Die Verbindung mit LinkedIn hat nicht geklappt. Bitte noch einmal versuchen.",
}


def _back(notice: str) -> RedirectResponse:
    return RedirectResponse(f"/linkedin?konto={notice}", status_code=_SEE_OTHER)


@router.get("/linkedin/connect")
def linkedin_connect(request: Request) -> Response:
    if not config.linkedin_configured():
        return _back("fehler")
    state = linkedin_link.new_state()
    response = RedirectResponse(linkedin_link.authorize_url(state), status_code=_SEE_OTHER)
    response.set_cookie(_LINKEDIN_STATE_COOKIE, state, max_age=600, httponly=True,
                        secure=request.url.scheme == "https", samesite="lax", path="/linkedin")
    return response


@router.get("/linkedin/callback")
def linkedin_callback(request: Request, code: str = "", state: str = "", error: str = "") -> Response:
    """LinkedIn's answer. The state gate first: a callback without this
    browser's state is not this browser's flow."""
    expected = request.cookies.get(_LINKEDIN_STATE_COOKIE, "")
    if not (state and expected and secrets.compare_digest(state.encode(), expected.encode())):
        _log.warning("LinkedIn callback refused: state did not match")
        response = _back("fehler")
    elif error:
        response = _back("abgebrochen" if error in ("user_cancelled_login", "user_cancelled_authorize")
                         else "fehler")
    elif not code:
        response = _back("fehler")
    else:
        try:
            linkedin_link.exchange(_owner(request), code)
            response = _back("verbunden")
        except linkedin_link.LinkedInError as exc:
            _log.error("LinkedIn connection failed: %s", exc)
            response = _back("fehler")
    response.delete_cookie(_LINKEDIN_STATE_COOKIE, path="/linkedin")
    return response


@router.post("/linkedin/disconnect")
def linkedin_disconnect(request: Request) -> Response:
    linkedin_link.disconnect(_owner(request))
    return _back("getrennt")


@router.post("/linkedin/{post_id}/publish")
def publish_post(post_id: int, request: Request, session: Session = Depends(get_db)) -> Response:
    post = _row_or_404(session, LinkedInPost, post_id)
    try:
        worklists.publish_post(session, post, _owner(request))
    except worklists.Invalid as exc:
        session.rollback()
        return _posts_page(request, session, error=str(exc))
    return RedirectResponse(f"/linkedin#post-{post.id}", status_code=_SEE_OTHER)


@router.post("/linkedin/{post_id}/schedule")
async def schedule_post(post_id: int, request: Request, session: Session = Depends(get_db)) -> Response:
    post = _row_or_404(session, LinkedInPost, post_id)
    try:
        worklists.schedule_post(session, post, _owner(request), await _form(request))
    except worklists.Invalid as exc:
        session.rollback()
        return _posts_page(request, session, error=str(exc))
    return RedirectResponse(f"/linkedin#post-{post.id}", status_code=_SEE_OTHER)


@router.post("/linkedin/{post_id}/published")
async def mark_published(post_id: int, request: Request, session: Session = Depends(get_db)) -> Response:
    post = _row_or_404(session, LinkedInPost, post_id)
    try:
        worklists.mark_published(session, post, await _form(request))
    except worklists.Invalid as exc:
        session.rollback()
        return _posts_page(request, session, error=str(exc))
    return RedirectResponse(f"/linkedin#post-{post.id}", status_code=_SEE_OTHER)


@router.post("/linkedin/{post_id}/unschedule")
def unschedule_post(post_id: int, session: Session = Depends(get_db)) -> Response:
    post = _row_or_404(session, LinkedInPost, post_id)
    worklists.unschedule_post(session, post)
    return RedirectResponse(f"/linkedin#post-{post.id}", status_code=_SEE_OTHER)


@router.post("/linkedin/{post_id}")
async def update_post(post_id: int, request: Request, session: Session = Depends(get_db)) -> Response:
    post = _row_or_404(session, LinkedInPost, post_id)
    form = await _form(request)
    try:
        if set(form) <= {"status"}:
            if form.get("status") not in POST_STATES:
                raise worklists.Invalid("Unbekannter Wert.")
            worklists.set_post_status(post, str(form["status"]))
            session.commit()
        else:
            worklists.save_post(session, form, post)
    except worklists.Invalid as exc:
        session.rollback()
        return _posts_page(request, session, error=str(exc))
    return RedirectResponse(f"/linkedin#post-{post.id}", status_code=_SEE_OTHER)


@router.post("/linkedin/{post_id}/delete")
def delete_post(post_id: int, session: Session = Depends(get_db)) -> Response:
    session.delete(_row_or_404(session, LinkedInPost, post_id))
    session.commit()
    return RedirectResponse("/linkedin", status_code=_SEE_OTHER)


# --- Sales CRM ------------------------------------------------------------------


def _deals_page(request: Request, session: Session, *, error: str = "", draft: dict | None = None) -> Response:
    rows = worklists.deals(session)
    columns = worklists.pipeline(rows)
    return render_react(request, "sales", dict(
        pipeline=[dict(c, deals=[_deal(d) for d in c["deals"]]) for c in columns],
        stages=[[s, worklists.DEAL_STAGE_LABELS[s]] for s in DEAL_STAGES],
        open_value=sum(c["value"] for c in columns if c["stage"] not in worklists.CLOSED_STAGES),
        error=error, draft=draft or {}))


@router.get("/sales")
def deals_view(request: Request, session: Session = Depends(get_db)) -> Response:
    return _deals_page(request, session)


@router.post("/sales")
async def create_deal(request: Request, session: Session = Depends(get_db)) -> Response:
    form = await _form(request)
    try:
        worklists.save_deal(session, form)
    except worklists.Invalid as exc:
        session.rollback()
        return _deals_page(request, session, error=str(exc), draft=form)
    return RedirectResponse("/sales", status_code=_SEE_OTHER)


@router.post("/sales/{deal_id}")
async def update_deal(deal_id: int, request: Request, session: Session = Depends(get_db)) -> Response:
    deal = _row_or_404(session, Deal, deal_id)
    form = await _form(request)
    try:
        if set(form) <= {"stage"}:
            worklists.set_deal_stage(deal, str(form.get("stage", "")))
            session.commit()
        else:
            worklists.save_deal(session, form, deal)
    except worklists.Invalid as exc:
        session.rollback()
        return _deals_page(request, session, error=str(exc))
    return RedirectResponse(f"/sales#deal-{deal.id}", status_code=_SEE_OTHER)


@router.post("/sales/{deal_id}/delete")
def delete_deal(deal_id: int, session: Session = Depends(get_db)) -> Response:
    session.delete(_row_or_404(session, Deal, deal_id))
    session.commit()
    return RedirectResponse("/sales", status_code=_SEE_OTHER)


@router.get('/api/v1/tasks/overdue')
def overdue_tasks(request: Request, session: Session = Depends(get_db)):
    import datetime as dt
    from zoneinfo import ZoneInfo
    member = worklists.member_for(request.scope.get('user_email'))
    today = dt.datetime.now(ZoneInfo('Europe/Zurich')).date()
    rows = worklists.overdue_for(session, member, today=today)
    return JSONResponse({'member':member, 'day':today.isoformat(), 'tasks':[
        {'id':t.id, 'title':t.title, 'due_on':t.due_on.isoformat(), 'days_overdue':(today-t.due_on).days,
         'href':f'/aufgaben?aufgabe={t.id}'} for t in rows]}, headers={'Cache-Control':'no-store'})
