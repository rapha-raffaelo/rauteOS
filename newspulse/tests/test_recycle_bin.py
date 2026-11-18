import datetime as dt
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from newspulse import recycle_bin
from newspulse.db import make_engine
from newspulse.models import Base,Task,TaskSubtask,TrashEntry

@pytest.fixture
def session():
    engine=make_engine('sqlite://')
    Base.metadata.create_all(engine)
    with Session(engine,expire_on_commit=False) as session:
        yield session


def test_cascade_restore_and_exact_expiry(session):
    task=Task(title='Kundenbriefing',status='review',subtasks=[TaskSubtask(title='Fakten prüfen')])
    session.add(task);session.commit();identity=task.id
    session.delete(task);session.commit()
    entry=session.scalar(select(TrashEntry))
    assert entry and len(entry.payload['rows'])==2
    assert session.scalar(select(TaskSubtask)) is None
    recycle_bin.restore(session,entry.id)
    restored=session.get(Task,identity)
    assert restored.status=='review' and restored.subtasks[0].title=='Fakten prüfen'
    session.delete(restored);session.commit()
    entry=session.scalar(select(TrashEntry))
    with pytest.raises(ValueError):recycle_bin.restore(session,entry.id,now=entry.expires_at)
    recycle_bin.purge(session,now=entry.expires_at)
    assert session.scalar(select(TrashEntry)) is None


def test_restore_conflict_never_overwrites_and_keeps_bin_entry(session):
    task=Task(title='Alte Aufgabe');session.add(task);session.commit();identity=task.id
    session.delete(task);session.commit();entry=session.scalar(select(TrashEntry))
    session.add(Task(id=identity,title='Neue Aufgabe'));session.commit()
    with pytest.raises(ValueError):recycle_bin.restore(session,entry.id)
    assert session.get(Task,identity).title=='Neue Aufgabe'
    assert session.get(TrashEntry,entry.id) is not None


def test_snapshot_rollback_does_not_leave_bin_entry(session):
    task=Task(title='Bleibt');session.add(task);session.commit()
    session.delete(task);session.flush();session.rollback()
    assert session.get(Task,task.id) is not None
    assert session.scalar(select(TrashEntry)) is None


def test_snapshot_codec_keeps_binary_dates_and_nested_values():
    data={'audio':b'\x00\xff','when':dt.datetime(2026,11,18,tzinfo=dt.UTC),'list':[{'day':dt.date(2026,11,18)}]}
    assert recycle_bin.decode(recycle_bin.encode(data))==data


def test_set_null_reference_is_restored_without_overwriting_changed_data(session):
    from newspulse.models import Client,Angle,Contact,Outreach
    client=Client(name='Test');session.add(client);session.flush()
    angle=Angle(client_id=client.id,subject='Thema',message='Pitch',context='Kontext')
    contact=Contact(name='Anna',outlet='Medium');session.add_all([angle,contact]);session.flush()
    letter=Outreach(client_id=client.id,angle_id=angle.id,contact_id=contact.id,subject='Angebot',message='Text')
    session.add(letter);session.commit();contact_id=contact.id
    session.delete(contact);session.commit();session.expire_all()
    assert letter.contact_id is None
    entry=session.scalar(select(TrashEntry))
    recycle_bin.restore(session,entry.id)
    assert session.get(Outreach,letter.id).contact_id==contact_id


def test_manual_client_archive_deletion_keeps_recoverable_data_until_original_expiry(session):
    from newspulse import clients
    from newspulse.models import Client
    client=clients.create_client(session,name='Archiviert')
    clients.deactivate_client(session,client.id)
    expiry=client.deactivated_at+recycle_bin.RETENTION
    clients.purge_archived(session,everything=True)
    entry=session.scalar(select(TrashEntry))
    assert entry.expires_at==expiry and session.get(Client,client.id) is None
    recycle_bin.restore(session,entry.id)
    assert session.get(Client,client.id).active is True


def test_removing_subtask_from_collection_is_recoverable(session):
    task=Task(title='Briefing',subtasks=[TaskSubtask(title='Quelle lesen')])
    session.add(task);session.commit();identity=task.id
    task.subtasks.clear();session.commit()
    entry=session.scalar(select(TrashEntry))
    assert entry.record_type=='task_subtasks'
    recycle_bin.restore(session,entry.id)
    assert session.get(Task,identity).subtasks[0].title=='Quelle lesen'
