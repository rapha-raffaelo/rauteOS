"""React Twin page inside the existing authenticated workspace shell."""
import datetime as dt
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from .. import frontend
from ..app import get_db, templates
from ..mandates import mandate_or_404
from .today import _fetch_last_run, _local_tz

router = APIRouter()


@router.get('/client/{client_id}/twin', response_class=HTMLResponse)
def twin_page(client_id: int, request: Request, session: Session = Depends(get_db)):
    client = mandate_or_404(session, client_id)
    return templates.TemplateResponse(request, 'client_twin.html', dict(
        client=client, frontend=frontend.page_assets('twin'),
        last_run=_fetch_last_run(session), header_date=dt.datetime.now(_local_tz()).date()))
