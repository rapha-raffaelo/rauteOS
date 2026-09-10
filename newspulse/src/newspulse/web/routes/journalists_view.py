"""React journalist workspace inside the authenticated application shell."""
import datetime as dt
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from .. import frontend
from ..app import get_db, templates
from .today import _fetch_last_run, _local_tz

router = APIRouter()


@router.get('/journalists')
def journalists_page(request: Request, session: Session = Depends(get_db)):
    return templates.TemplateResponse(request, 'journalists_react.html', dict(
        frontend=frontend.page_assets('journalists'), last_run=_fetch_last_run(session),
        header_date=dt.datetime.now(_local_tz()).date()))
