"""Unified opportunity workspace and explicit idea development requests."""
import datetime as dt
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.orm.exc import StaleDataError
from ... import opportunity_development, workspaces
from ...models import Contact, JournalistProfile, OpportunityDevelopment, OpportunityEvent, OpportunityWorkspace
from ..app import get_db
from ..mandates import mandate_or_404
from ..spawn import start_or_release
from .assets_view import occasion_for_opportunity

router=APIRouter(prefix='/api/v1/clients/{client_id}/opportunities',tags=['opportunities'])
Kind=Literal['detected','developed']


class Choices(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    revision:int=Field(ge=0)
    storyline:str=Field(default='',max_length=5000)
    speaker_statement_id:int|None=Field(default=None,gt=0)
    contact_ids:list[int]=Field(default_factory=list,max_length=30)


class DevelopInput(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    focus:str=Field(min_length=3,max_length=300)


def development_data(row):
    return {key:getattr(row,key) for key in ('id','focus','status','started_at','finished_at','queries','sources','workspace_ids','note')}


@router.get('')
def listing(client_id:int,response:Response,session:Session=Depends(get_db)):
    client=mandate_or_404(session,client_id)
    response.headers['Cache-Control']='no-store'
    job=session.scalar(select(OpportunityDevelopment).where(OpportunityDevelopment.client_id==client_id)
                       .order_by(OpportunityDevelopment.id.desc()).limit(1))
    return dict(client=dict(id=client.id,name=client.name),opportunities=workspaces.listings(session,client_id),
                development=development_data(job) if job else None)


def failed(factory,identity):
    with factory() as session:
        session.execute(update(OpportunityDevelopment).where(OpportunityDevelopment.id==identity,
            OpportunityDevelopment.status=='running').values(status='failed',finished_at=dt.datetime.now(dt.UTC),
            note='Die Entwicklung konnte nicht abgeschlossen werden. Bitte erneut versuchen.'))
        session.commit()


def worker(factory,identity):
    try:
        with factory() as session:opportunity_development.develop(session,identity)
    except Exception:
        failed(factory,identity)


@router.post('/develop',status_code=202)
def start_development(client_id:int,body:DevelopInput,session:Session=Depends(get_db)):
    mandate_or_404(session,client_id)
    now=dt.datetime.now(dt.UTC)
    session.execute(update(OpportunityDevelopment).where(OpportunityDevelopment.client_id==client_id,
        OpportunityDevelopment.status=='running',OpportunityDevelopment.started_at<now-dt.timedelta(minutes=20))
        .values(status='failed',finished_at=now,note='Entwicklung unterbrochen oder Zeitlimit überschritten.'))
    row=OpportunityDevelopment(client_id=client_id,focus=body.focus)
    session.add(row)
    try:session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(409,'Für diesen Mandanten läuft bereits eine Entwicklung.')
    result=development_data(row)
    factory=sessionmaker(bind=session.get_bind(),expire_on_commit=False)
    try:start_or_release(worker,args=(factory,row.id),name=f'opportunity-development-{row.id}',release=lambda:failed(factory,row.id))
    except RuntimeError:raise HTTPException(503,'Entwicklung konnte nicht gestartet werden.')
    return result


@router.get('/{kind}/{identity}')
def read_workspace(client_id:int,kind:Kind,identity:int,response:Response,session:Session=Depends(get_db)):
    mandate_or_404(session,client_id)
    response.headers['Cache-Control']='no-store'
    result=workspaces.read(session,client_id,kind,identity)
    if result is None:raise HTTPException(404,'Gelegenheit nicht gefunden.')
    return result


def save_choices(session,client_id,kind,identity,body,actor,activate=False):
    client=mandate_or_404(session,client_id)
    anchor=workspaces.anchor(session,client_id,kind,identity)
    if anchor is None:raise HTTPException(404,'Gelegenheit nicht gefunden.')
    if workspaces.ended(anchor,kind,dt.datetime.now(dt.UTC)):
        raise HTTPException(409,'Diese Gelegenheit ist abgeschlossen.')
    row=workspaces.stored(session,client_id,kind,identity)
    if (row.revision if row else 0)!=body.revision:
        raise HTTPException(409,'Workspace wurde inzwischen geändert. Neu laden und vergleichen.')
    if body.speaker_statement_id and body.speaker_statement_id not in {r.id for r in workspaces.speakers(session,client_id)}:
        raise HTTPException(422,'Sprecher ist nicht im verwendbaren Twin hinterlegt.')
    contacts=set(session.scalars(select(Contact.id).where(Contact.id.in_(body.contact_ids))))
    blocked=set(session.scalars(select(JournalistProfile.contact_id).where(JournalistProfile.contact_id.in_(body.contact_ids),
        JournalistProfile.relationship_status=='Nicht kontaktieren')))
    if set(body.contact_ids)!=contacts or blocked:
        raise HTTPException(422,'Ein Kontakt fehlt oder darf nicht kontaktiert werden.')
    if activate and not body.storyline:
        raise HTTPException(422,'Vor der Aktivierung eine Storyline auswählen oder formulieren.')
    # The existing helper resolves a detected opportunity to exactly one Angle.
    # Call before adding the workspace because the helper owns its commit.
    angle=occasion_for_opportunity(session,client,anchor) if activate and kind=='detected' else anchor if kind=='developed' else None
    if row is not None:
        session.refresh(row)
        if row.revision!=body.revision:
            raise HTTPException(409,'Workspace wurde inzwischen geändert. Neu laden und vergleichen.')
        row.revision+=1
    was_active=row is not None and row.status=='active'
    if row is None:
        row=OpportunityWorkspace(client_id=client_id,context_kind=kind,context_id=identity)
        session.add(row)
    row.storyline=body.storyline
    row.speaker_statement_id=body.speaker_statement_id
    row.contact_ids=list(dict.fromkeys(body.contact_ids))
    if angle:row.angle_id=angle.id
    if activate:row.status='active'
    try:
        session.flush()
        session.add(OpportunityEvent(workspace_id=row.id,kind='activated' if activate and not was_active else 'choices_saved',actor=actor,
            detail=dict(storyline=row.storyline,speaker_statement_id=row.speaker_statement_id,contact_ids=row.contact_ids)))
        session.commit()
    except (IntegrityError,StaleDataError):
        session.rollback()
        raise HTTPException(409,'Workspace wurde inzwischen geändert. Neu laden und vergleichen.')
    return workspaces.read(session,client_id,kind,identity)


@router.put('/{kind}/{identity}')
def update_workspace(client_id:int,kind:Kind,identity:int,body:Choices,request:Request,session:Session=Depends(get_db)):
    return save_choices(session,client_id,kind,identity,body,str(request.scope.get('user_email') or 'mensch')[:200])


@router.post('/{kind}/{identity}/activate')
def activate_workspace(client_id:int,kind:Kind,identity:int,body:Choices,request:Request,session:Session=Depends(get_db)):
    return save_choices(session,client_id,kind,identity,body,str(request.scope.get('user_email') or 'mensch')[:200],activate=True)
