"""Agency recycle bin; restoration and deliberate permanent deletion."""
import datetime as dt
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, defer
from ... import clients, recycle_bin, config
from ...models import Client, TrashEntry
from ..app import get_db, templates

router = APIRouter()

@router.get('/trash')
def page(request: Request, session: Session = Depends(get_db)):
    recycle_bin.purge(session)
    clients.purge_archived(session)
    entries = list(session.scalars(select(TrashEntry).options(defer(TrashEntry.payload)).order_by(TrashEntry.deleted_at.desc())))
    archived = list(session.scalars(select(Client).where(Client.active.is_(False),Client.is_competitor.is_(False))))
    names = {c.id:c.name for c in session.scalars(select(Client))}
    return templates.TemplateResponse(request,'trash.html',dict(entries=entries,archived=archived,client_names=names,local_zone=config.LOCAL_ZONE,header_date=dt.datetime.now(config.LOCAL_ZONE).date(),last_run=None))

@router.post('/trash/{entry_id}/restore')
def restore(entry_id: int, session: Session = Depends(get_db)):
    try: recycle_bin.restore(session,entry_id)
    except ValueError as exc: raise HTTPException(409,str(exc)) from exc
    return RedirectResponse('/trash',status_code=303)

@router.post('/trash/{entry_id}/delete')
def remove(entry_id: int, session: Session = Depends(get_db)):
    session.execute(delete(TrashEntry).where(TrashEntry.id==entry_id))
    session.commit()
    return RedirectResponse('/trash',status_code=303)

@router.post('/trash/client/{client_id}/restore')
def restore_client(client_id: int, session: Session = Depends(get_db)):
    client = session.get(Client,client_id)
    if client is None or client.active or client.is_competitor or not client.deactivated_at:
        raise HTTPException(404,'Kunde nicht im Papierkorb.')
    if client.deactivated_at + recycle_bin.RETENTION <= dt.datetime.now(dt.UTC):
        raise HTTPException(409,'Die Aufbewahrungsfrist ist abgelaufen.')
    try: clients.update_client(session,client_id,active=True)
    except ValueError as exc: raise HTTPException(409,str(exc)) from exc
    return RedirectResponse('/trash',status_code=303)
