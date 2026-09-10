"""Create or review drafts in an opportunity; never sends a message."""
import datetime as dt
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException,Response
from pydantic import BaseModel,ConfigDict,Field
from sqlalchemy import select,update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session,sessionmaker
from ... import activation,asset_evidence,assets,prose,workspaces
from ...models import Angle,Client,Asset,OpportunityAssetRun,OpportunityEvent,OpportunityWorkspace,Outreach
from ..app import get_db
from ..mandates import mandate_or_404
from ..spawn import start_or_release

router=APIRouter(prefix='/api/v1/clients/{client_id}/opportunities/{kind}/{identity}/activation',tags=['activation'])
Kind=Literal['detected','developed']


class DraftInput(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    kind:str=Field(max_length=40)
    contact_id:int|None=Field(default=None,gt=0)
    instruction:str=Field(default='',max_length=5000)


class TextInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    digest:str=Field(min_length=64,max_length=64)
    title:str=Field(max_length=1000)
    body:str=Field(min_length=1,max_length=40000)


def workspace_or_404(session,client_id,kind,identity):
    mandate_or_404(session,client_id)
    if workspaces.anchor(session,client_id,kind,identity) is None:raise HTTPException(404,'Gelegenheit nicht gefunden.')
    row=workspaces.stored(session,client_id,kind,identity)
    if row is None:raise HTTPException(409,'Bitte zuerst Storyline und Auswahl im Workspace speichern.')
    return row


def failed(factory,identity):
    with factory() as session:
        session.execute(update(OpportunityAssetRun).where(OpportunityAssetRun.id==identity,OpportunityAssetRun.status=='running')
            .values(status='failed',finished_at=dt.datetime.now(dt.UTC),note='Der Arbeitsschritt konnte nicht abgeschlossen werden. Vorhandene Texte bleiben erhalten.'))
        session.commit()


def worker(factory,identity):
    try:
        with factory() as session:activation.run(session,identity)
    except Exception:failed(factory,identity)


def launch(session,workspace,kind,context,*,asset_id=None,outreach_id=None):
    now=dt.datetime.now(dt.UTC)
    session.execute(update(OpportunityAssetRun).where(OpportunityAssetRun.workspace_id==workspace.id,
        OpportunityAssetRun.status=='running',OpportunityAssetRun.started_at<now-dt.timedelta(minutes=20))
        .values(status='failed',finished_at=now,note='Arbeitsschritt unterbrochen oder Zeitlimit überschritten.'))
    job=OpportunityAssetRun(workspace_id=workspace.id,kind=kind,context=context,asset_id=asset_id,outreach_id=outreach_id)
    session.add(job)
    try:session.commit()
    except IntegrityError:
        session.rollback();raise HTTPException(409,'Für diese Gelegenheit läuft bereits ein Arbeitsschritt.')
    identity=job.id
    factory=sessionmaker(bind=session.get_bind(),expire_on_commit=False)
    try:start_or_release(worker,args=(factory,identity),name=f'opportunity-asset-{identity}',release=lambda:failed(factory,identity))
    except RuntimeError:raise HTTPException(503,'Arbeitsschritt konnte nicht gestartet werden.')
    return {'id':identity,'status':'running'}


@router.get('')
def read(client_id:int,kind:Kind,identity:int,response:Response,session:Session=Depends(get_db)):
    workspace=workspace_or_404(session,client_id,kind,identity)
    response.headers['Cache-Control']='no-store'
    return activation.read(session,workspace)


@router.post('',status_code=202)
def generate(client_id:int,kind:Kind,identity:int,body:DraftInput,session:Session=Depends(get_db)):
    workspace=workspace_or_404(session,client_id,kind,identity)
    anchor=workspaces.anchor(session,client_id,kind,identity)
    if workspaces.ended(anchor,kind,dt.datetime.now(dt.UTC)):raise HTTPException(409,'Gelegenheit ist abgeschlossen.')
    if body.kind not in dict(activation.FORMATS):raise HTTPException(422,'Unbekanntes Format.')
    if workspace.angle_id is None:raise HTTPException(409,'Bitte die Gelegenheit zuerst aktivieren.')
    if body.kind=='custom' and not body.instruction:raise HTTPException(422,'Bitte den eigenen Auftrag beschreiben.')
    if body.kind in {'pitch','interviewangebot','interview_briefing'} and not body.contact_id:
        raise HTTPException(422,'Bitte einen ausgewählten Journalisten angeben.')
    if body.contact_id and body.contact_id not in workspace.contact_ids:
        raise HTTPException(422,'Journalist ist nicht im Workspace ausgewählt.')
    if body.contact_id and body.kind not in {'pitch','interviewangebot','interview_briefing'}:
        raise HTTPException(422,'Dieses Format hat keinen Journalisten als Empfänger.')
    try:context,target=activation.context_for(session,workspace,contact_id=body.contact_id,instruction=body.instruction)
    except ValueError as exc:raise HTTPException(422,str(exc))
    if body.kind!='pitch':
        fmt=assets.REGISTRY[body.kind]
        if fmt.speaker_key and not context['speaker']:
            raise HTTPException(422,'Bitte zuerst einen Sprecher im Workspace auswählen.')
        ready=assets.requirements_met(session,fmt,session.get(Client,client_id),session.get(Angle,workspace.angle_id),
            facts=activation.writing_facts(session,workspace,context),target=target)
        if not ready.ok:raise HTTPException(422,ready.reason)
    return launch(session,workspace,body.kind,body.model_dump())


def linked_text(session,workspace,text_type,text_id):
    column=OpportunityAssetRun.asset_id if text_type=='asset' else OpportunityAssetRun.outreach_id
    job=session.scalar(select(OpportunityAssetRun).where(OpportunityAssetRun.workspace_id==workspace.id,column==text_id)
                       .order_by(OpportunityAssetRun.id.desc()).limit(1))
    row=activation.text_row(session,job) if job else None
    if row is None or row.client_id!=workspace.client_id:raise HTTPException(404,'Text nicht gefunden.')
    return job,row


@router.post('/{text_type}/{text_id}/check',status_code=202)
def recheck(client_id:int,kind:Kind,identity:int,text_type:Literal['asset','outreach'],text_id:int,session:Session=Depends(get_db)):
    workspace=workspace_or_404(session,client_id,kind,identity)
    previous,row=linked_text(session,workspace,text_type,text_id)
    if row.released_at:raise HTTPException(409,'Ein freigegebener Text ist unveränderlich.')
    return launch(session,workspace,previous.kind,dict(operation='check',contact_id=previous.context.get('contact_id')),
        asset_id=row.id if text_type=='asset' else None,outreach_id=row.id if text_type=='outreach' else None)


@router.put('/{text_type}/{text_id}')
def edit(client_id:int,kind:Kind,identity:int,text_type:Literal['asset','outreach'],text_id:int,body:TextInput,session:Session=Depends(get_db)):
    workspace=workspace_or_404(session,client_id,kind,identity)
    previous,row=linked_text(session,workspace,text_type,text_id)
    if row.released_at:raise HTTPException(409,'Ein freigegebener Text ist unveränderlich.')
    title,content=activation.text_parts(row)
    if asset_evidence.digest(title,content)!=body.digest:raise HTTPException(409,'Text wurde inzwischen geändert. Neu laden und vergleichen.')
    # Compare both text columns in the UPDATE, so a concurrently finishing
    # writer cannot be overwritten after a stale in-memory comparison.
    if text_type=='asset':
        stmt=update(Asset).where(Asset.id==row.id,Asset.title==title,Asset.body==content,Asset.released_at.is_(None)).values(
            title=prose.plain(body.title),body=prose.plain(body.body),edited_at=dt.datetime.now(dt.UTC),review='',reviewed_by='',guide_review='',guide_reviewed_by='')
    else:
        stmt=update(Outreach).where(Outreach.id==row.id,Outreach.subject==title,Outreach.message==content,Outreach.released_at.is_(None)).values(
            subject=prose.plain(body.title),message=prose.plain(body.body),review='',reviewed_by='',guide_review=[],guide_reviewed_by='')
    if session.execute(stmt.execution_options(synchronize_session=False)).rowcount!=1:
        session.rollback();raise HTTPException(409,'Text wurde inzwischen geändert. Neu laden und vergleichen.')
    session.add(OpportunityEvent(workspace_id=workspace.id,kind='text_edited',detail=dict(type=text_type,id=text_id)))
    session.commit();session.expire_all()
    return activation.read(session,workspace)
