"""The pages of spec 10: Aufgaben, LinkedIn and Sales CRM.

Plain forms that post and redirect back, like the archive and settings pages.
A value that cannot be stored re-renders the page with the reason and the
typed fields kept, rather than redirecting it away.
"""

from __future__ import annotations

import logging
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session

from ... import config, linkedin_link, worklists, workspaces
from ...models import DEAL_STAGES, POST_STATES, TASK_PRIORITIES, TASK_STATES, Asset, Deal, LinkedInPost, Task
from ..app import get_db
from ..react_pages import render as render_react

router = APIRouter()
_log = logging.getLogger(__name__)
_SEE_OTHER = 303
_LINKEDIN_STATE_COOKIE = "newspulse_linkedin_state"


def _clients(session: Session) -> list[dict]:
    return [dict(id=c.id, name=c.name) for c in worklists.mandates(session)]


def _task(t: Task) -> dict:
    return dict(id=t.id, title=t.title, note=t.note, priority=t.priority, status=t.status,
                due_on=t.due_on, owner=t.owner, context_href=t.context_href,
                client=dict(id=t.client.id, name=t.client.name) if t.client else None,
                created_at=t.created_at, done_at=t.done_at)


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
    return {k: v for k, v in (await request.form()).items()}


# --- Aufgaben -------------------------------------------------------------------


def _tasks_page(request: Request, session: Session, *, error: str = "", draft: dict | None = None) -> Response:
    status = request.query_params.get("status", "")
    status = status if status in TASK_STATES else ""
    raw = request.query_params.get("client", "")
    client_id = int(raw) if raw.isdigit() else None
    rows = worklists.tasks(session, status=status, client_id=client_id)
    # Over every open task, whatever the filter: the same number as the sidebar.
    everything = worklists.open_tasks(session)
    return render_react(request, "tasks", dict(
        tasks=[_task(t) for t in rows], clients=_clients(session),
        open_total=len(everything), due_on=[t.due_on for t in everything if t.due_on],
        priorities=[[p, worklists.TASK_PRIORITY_LABELS[p]] for p in TASK_PRIORITIES],
        states=[[s, worklists.TASK_STATE_LABELS[s]] for s in TASK_STATES],
        filter=dict(status=status, client=client_id), error=error, draft=draft or {}))


@router.get("/aufgaben")
def tasks_view(request: Request, session: Session = Depends(get_db)) -> Response:
    return _tasks_page(request, session)


@router.post("/aufgaben")
async def create_task(request: Request, session: Session = Depends(get_db)) -> Response:
    form = await _form(request)
    try:
        worklists.save_task(session, form)
    except worklists.Invalid as exc:
        session.rollback()
        return _tasks_page(request, session, error=str(exc), draft=form)
    return RedirectResponse("/aufgaben", status_code=_SEE_OTHER)


@router.post("/aufgaben/{task_id}")
async def update_task(task_id: int, request: Request, session: Session = Depends(get_db)) -> Response:
    task = _row_or_404(session, Task, task_id)
    form = await _form(request)
    try:
        if set(form) <= {"status"}:  # the one-click status buttons
            worklists.set_task_status(task, str(form.get("status", "")))
            session.commit()
        else:
            worklists.save_task(session, form, task)
    except worklists.Invalid as exc:
        session.rollback()
        return _tasks_page(request, session, error=str(exc))
    return RedirectResponse("/aufgaben", status_code=_SEE_OTHER)


@router.post("/aufgaben/{task_id}/delete")
def delete_task(task_id: int, session: Session = Depends(get_db)) -> Response:
    session.delete(_row_or_404(session, Task, task_id))
    session.commit()
    return RedirectResponse("/aufgaben", status_code=_SEE_OTHER)


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
