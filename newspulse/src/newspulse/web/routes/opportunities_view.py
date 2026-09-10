"""React opportunity list and workspace, sharing the existing authenticated shell."""
import datetime as dt
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from .. import frontend
from ..app import get_db,templates
from ..mandates import mandate_or_404
from .today import _fetch_last_run,_local_tz
router=APIRouter()


@router.get('/client/{client_id}/opportunities')
def page(client_id:int,request:Request,session:Session=Depends(get_db)):
    client=mandate_or_404(session,client_id)
    return templates.TemplateResponse(request,'opportunities_react.html',dict(client=client,
        frontend=frontend.page_assets('opportunities'),last_run=_fetch_last_run(session),
        header_date=dt.datetime.now(_local_tz()).date()))
