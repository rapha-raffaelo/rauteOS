"""Transactional deletion snapshots. Restore never overwrites newer records."""
import base64
import datetime as dt
import decimal
import uuid
from sqlalchemy import and_, delete, insert, inspect, select, update
from sqlalchemy.exc import IntegrityError
from .models import Base, TrashEntry

RETENTION = dt.timedelta(weeks=12)
# Credentials and transient configuration are never exposed in the recycle bin.
EXCLUDED = {'trash_entries', 'settings', 'ai_models', 'twin_import_previews', 'dismissed_task_sources'}


def encode(value):
    if isinstance(value, (dt.datetime, dt.date, bytes, decimal.Decimal, uuid.UUID)):
        kind = type(value).__name__
        data = base64.b64encode(value).decode() if isinstance(value, bytes) else value.isoformat() if isinstance(value, (dt.datetime, dt.date)) else str(value)
        return {'__trash_type': kind, 'value': data}
    if isinstance(value, dict): return {k: encode(v) for k,v in value.items()}
    if isinstance(value, (list,tuple)): return [encode(v) for v in value]
    return value


def decode(value):
    if isinstance(value, list): return [decode(v) for v in value]
    if isinstance(value, dict):
        if set(value) == {'__trash_type','value'}:
            loaders = {'datetime':dt.datetime.fromisoformat,'date':dt.date.fromisoformat,
                       'bytes':base64.b64decode,'Decimal':decimal.Decimal,'UUID':uuid.UUID}
            if value['__trash_type'] in loaders: return loaders[value['__trash_type']](value['value'])
        return {k:decode(v) for k,v in value.items()}
    return value


def identity(table, row):
    return tuple(row[c.name] for c in table.primary_key)


def where_pk(table, row):
    return and_(*(c == row[c.name] for c in table.primary_key))


def snapshot(connection, table, root):
    rows, links, seen = [], [], set()
    incoming = {}
    for child in Base.metadata.tables.values():
        if child.name in EXCLUDED: continue
        for fk in child.foreign_keys:
            incoming.setdefault(fk.column.table.name, []).append((child,fk))
    def visit(current, value):
        key = (current.name, identity(current,value))
        if key in seen: return
        seen.add(key)
        rows.append({'table':current.name, 'row':encode(dict(value))})
        if current.name in {'assets','outreach'}:
            tasks = Base.metadata.tables['tasks']
            kind = 'asset' if current.name=='assets' else 'outreach'
            for task in connection.execute(select(tasks).where(tasks.c.source_key==f'{kind}:{value["id"]}')).mappings():
                visit(tasks,task)
        for child,fk in incoming.get(current.name, []):
            dependents = connection.execute(select(child).where(fk.parent == value[fk.column.name])).mappings().all()
            for dependent in dependents:
                if fk.ondelete == 'CASCADE' or (current.name in {'assets','outreach'} and child.name=='opportunity_asset_runs'): visit(child,dependent)
                elif fk.ondelete == 'SET NULL':
                    links.append({'table':child.name,'pk':encode({c.name:dependent[c.name] for c in child.primary_key}),
                                  'column':fk.parent.name,'value':encode(dependent[fk.parent.name]),
                                  'guard':encode({c.name:dependent[c.name] for c in child.columns if not c.foreign_keys})})
    visit(table,root)
    return {'rows':rows,'links':links}, seen


def capture_deleted(session):
    """Called before ORM deletes, in the same transaction as the deletion."""
    removed, added = set(), set()
    for parent in session.dirty:
        state = inspect(parent)
        for relation in state.mapper.relationships:
            if relation.cascade.delete_orphan:
                history = state.attrs[relation.key].history
                removed.update(history.deleted)
                added.update(history.added)
    pending = [obj for obj in set(session.deleted) | (removed-added)
               if inspect(obj).mapper.local_table.name not in EXCLUDED]
    if not pending: return
    connection = session.connection()
    covered = set()
    # Capture parent roots before their ORM cascade children.
    order = {table.name:i for i,table in enumerate(Base.metadata.sorted_tables)}
    for obj in sorted(pending,key=lambda obj:(inspect(obj).mapper.local_table.name not in {'assets','outreach'},order.get(inspect(obj).mapper.local_table.name,0))):
        table = inspect(obj).mapper.local_table
        pk = {c.name:getattr(obj,c.name) for c in table.primary_key}
        if (table.name,tuple(pk.values())) in covered: continue
        row = connection.execute(select(table).where(where_pk(table,pk))).mappings().first()
        if row is None: continue
        payload, captured = snapshot(connection,table,row)
        covered.update(captured)
        now = dt.datetime.now(dt.UTC)
        title = next((str(row[k]) for k in ('title','subject','name','value','question_key') if row.get(k)), table.name)
        session.add(TrashEntry(title=title[:500],record_type=table.name,client_id=row.get('client_id'),
                               deleted_at=now,expires_at=now+RETENTION,payload=payload))


def purge(session, now=None):
    now = now or dt.datetime.now(dt.UTC)
    session.execute(delete(TrashEntry).where(TrashEntry.expires_at <= now))
    session.commit()


def restore(session, entry_id, now=None):
    now = now or dt.datetime.now(dt.UTC)
    entry = session.get(TrashEntry,entry_id)
    if entry is None or entry.expires_at <= now: raise ValueError('Dieser Eintrag ist nicht mehr wiederherstellbar.')
    try:
        # Claim atomically. Any insert conflict rolls the entire restore back.
        if session.execute(delete(TrashEntry).where(TrashEntry.id==entry.id,TrashEntry.expires_at>now)).rowcount != 1:
            raise ValueError('Der Eintrag wurde bereits bearbeitet.')
        order = {table.name:i for i,table in enumerate(Base.metadata.sorted_tables)}
        for item in sorted(entry.payload['rows'],key=lambda item:order[item['table']]):
            table = Base.metadata.tables[item['table']]
            values = decode(item['row'])
            if item['table']=='clients':
                from . import clients
                if clients._find_active_duplicate(session,clients._normalize_name(values['name']),exclude_id=values['id']) is not None:
                    raise ValueError('Ein aktiver Kunde mit diesem Namen existiert bereits. Vorhandene Daten wurden nicht überschrieben.')
                values['active'] = True
                values['deactivated_at'] = None
            session.execute(insert(table).values(**values))
        for link in entry.payload.get('links',[]):
            table = Base.metadata.tables[link['table']]
            current = session.connection().execute(select(table).where(where_pk(table,decode(link['pk'])))).mappings().first()
            if current is None or any(current[k]!=v for k,v in decode(link.get('guard',{})).items()):
                continue
            session.execute(update(table).where(where_pk(table,decode(link['pk'])),table.c[link['column']].is_(None))
                            .values({link['column']:decode(link['value'])}))
        # A deleted generated task must become eligible to remain visible again.
        for item in entry.payload['rows']:
            if item['table']=='tasks':
                source = decode(item['row']).get('source_key')
                if source:
                    from .models import DismissedTaskSource
                    session.execute(delete(DismissedTaskSource).where(DismissedTaskSource.source_key==source))
        session.commit()
        session.expire_all()
    except ValueError:
        session.rollback()
        raise
    except IntegrityError as exc:
        session.rollback()
        raise ValueError('Wiederherstellung nicht möglich: Ein verknüpfter Datensatz fehlt oder ein neuerer Eintrag belegt bereits denselben Platz. Vorhandene Daten wurden nicht überschrieben.') from exc
