"""Human workflow records attached to an existing Thema, never simulated mail."""
from __future__ import annotations

import datetime as dt
from copy import deepcopy

from sqlalchemy import select,update
from . import asset_evidence
from .models import Asset, OpportunityEvent, OpportunityAssetRun, Outreach, OutreachState, JournalistProfile


def content_key(row):
    return f"{'asset' if isinstance(row, Asset) else 'outreach'}-{row.id}"


def digest(row):
    return asset_evidence.digest(row.title, row.body) if isinstance(row, Asset) else asset_evidence.digest(row.subject, row.message)


def read(session, workspace, *, assets=None):
    data = deepcopy((workspace.data or {}).get('workflow', {})) if workspace else {}
    approvals = data.get('approvals', {})
    for value in approvals.values():
        value['stale'] = True
    if workspace and workspace.angle_id:
        if assets is None:
            assets = session.scalars(select(Asset).where(Asset.client_id == workspace.client_id, Asset.angle_id == workspace.angle_id))
        for row in assets:
            key = content_key(row)
            if key in approvals:
                approvals[key]['stale'] = approvals[key].get('digest') != digest(row)
    data['approvals'] = approvals
    data.setdefault('followups', {})
    return data


def summary(session, workspace, *, assets=None, letters=None):
    if not workspace:
        return dict(step='anlass', label='Neu', completed=False)
    flow = read(session, workspace, assets=assets)
    if flow.get('completed_at'):
        return dict(step='ergebnis', label='Abgeschlossen', completed=True)
    if assets is None:
        assets = list(session.scalars(select(Asset).where(Asset.client_id == workspace.client_id, Asset.angle_id == workspace.angle_id))) if workspace.angle_id else []
    if letters is None:
        letters = list(session.scalars(select(Outreach).where(Outreach.client_id == workspace.client_id, Outreach.angle_id == workspace.angle_id))) if workspace.angle_id else []
    exclusive=flow.get('exclusive',{})
    if exclusive.get('until') and not exclusive.get('released_at') and dt.datetime.fromisoformat(exclusive['until']) <= dt.datetime.now(dt.UTC):
        return dict(step='pitches',label='Exklusivfrist abgelaufen',completed=False)
    if any(research.get('status')=='ready' for research in flow.get('research',{}).values()):
        return dict(step='followup',label='Follow-up bereit',completed=False)
    if any(row.released_at for row in letters):
        return dict(step='followup', label='In Ansprache', completed=False)
    if letters:
        return dict(step='pitches', label='Pitches vorbereiten', completed=False)
    if any(a.get('status') == 'approved' and not a.get('stale') for a in flow['approvals'].values()):
        return dict(step='journalisten', label='Kundenfreigabe erfasst', completed=False)
    if assets:
        return dict(step='freigabe', label='Freigabe offen', completed=False)
    if workspace.status == 'active':
        return dict(step='assets', label='In Entwicklung', completed=False)
    return dict(step='blickwinkel', label='Blickwinkel wählen', completed=False)


def record(session, workspace, body, actor):
    """Validate first; caller commits workflow, canonical outcome and event atomically."""
    data = deepcopy(workspace.data or {})
    flow = deepcopy(data.get('workflow', {}))
    now = dt.datetime.now(dt.UTC)
    stamp = now.isoformat()
    if flow.get('completed_at') and body.action != 'reopen':
        raise ValueError('Das Thema ist abgeschlossen. Bitte zuerst wieder öffnen.')
    if body.action in {'approval', 'pitch_approval', 'sent', 'followup', 'outcome'} and body.text_id is None:
        raise ValueError('Bitte einen Text angeben.')
    if body.action == 'approval':
        row = session.get(Asset, body.text_id)
        if row is None or row.client_id != workspace.client_id or row.angle_id != workspace.angle_id:
            raise ValueError('Dieses Asset gehört nicht zum Thema.')
        if body.digest != digest(row):
            raise ValueError('Der Text wurde inzwischen geändert. Bitte neu laden und vergleichen.')
        if session.execute(update(Asset).where(Asset.id == row.id, Asset.title == row.title, Asset.body == row.body).values(title=row.title)).rowcount != 1:
            raise ValueError('Der Text wurde inzwischen geändert. Bitte neu laden und vergleichen.')
        if body.status not in {'internal', 'waiting', 'changes', 'approved'}:
            raise ValueError('Unbekannter Freigabestand.')
        if body.status == 'approved' and (not body.reviewer or not body.note):
            raise ValueError('Bitte die freigebende Person und den Nachweis der Zustimmung angeben.')
        if body.status == 'changes' and not body.note:
            raise ValueError('Bitte den Änderungswunsch eintragen.')
        flow.setdefault('approvals', {})[content_key(row)] = dict(status=body.status, digest=body.digest,
            reviewer=body.reviewer, note=body.note, actor=actor, updated_at=stamp)
    elif body.action in {'pitch_approval', 'sent'}:
        row = session.get(Outreach, body.text_id)
        if row is None or row.client_id != workspace.client_id or row.angle_id != workspace.angle_id:
            raise ValueError('Dieses Anschreiben gehört nicht zum Thema.')
        if row.released_at:
            raise ValueError('Für dieses Anschreiben ist der Versand bereits erfasst.')
        if body.digest != digest(row):
            raise ValueError('Der Pitch wurde inzwischen geändert. Bitte erneut prüfen.')
        # The conditional write also locks this text for the rest of the transaction.
        locked = session.execute(update(Outreach).where(Outreach.id == row.id,
            Outreach.subject == row.subject, Outreach.message == row.message,
            Outreach.released_at.is_(None)).values(subject=row.subject))
        if locked.rowcount != 1:
            raise ValueError('Der Pitch wurde inzwischen geändert. Bitte erneut prüfen.')
        if body.action == 'pitch_approval':
            if not body.reviewer or not body.note:
                raise ValueError('Bitte die freigebende Person und den Nachweis der Zustimmung angeben.')
            flow.setdefault('pitch_approvals', {})[str(row.id)] = dict(digest=body.digest,
                reviewer=body.reviewer, note=body.note, actor=actor, updated_at=stamp)
            row.client_ok_at = now
            row.client_ok_by = body.reviewer[:80]
        else:
            from .topic_automation import gate
            gate(session, row)
            approval = flow.get('pitch_approvals', {}).get(str(row.id), {})
            if approval.get('digest') != digest(row) or not row.client_ok_at:
                raise ValueError('Bitte zuerst die Kundenfreigabe für diese Pitch-Fassung erfassen.')
            if not body.note:
                raise ValueError('Bitte angeben, wann und über welchen Weg dieser Pitch versendet wurde.')
            profile = session.get(JournalistProfile, row.contact_id) if row.contact_id else None
            if profile and profile.relationship_status == 'Nicht kontaktieren':
                raise ValueError('Dieser Kontakt darf nicht kontaktiert werden.')
            if flow.get('exclusive', {}).get('text_id') == row.id:
                flow['exclusive']['until'] = (now + dt.timedelta(hours=24)).isoformat()
            row.released_at = now
            row.released_by = actor[:80]
            row.state = OutreachState.RAUS
            flow.setdefault('dispatches', {})[str(row.id)] = dict(note=body.note, actor=actor, recorded_at=stamp)
    elif body.action in {'followup', 'outcome'}:
        row = session.get(Outreach, body.text_id)
        if row is None or row.client_id != workspace.client_id or row.angle_id != workspace.angle_id or not row.released_at:
            raise ValueError('Für diesen Pitch ist noch kein Versand erfasst.')
        if body.action == 'outcome':
            if body.status not in {'antwort', 'absage', 'veroeffentlicht'} or not body.note:
                raise ValueError('Bitte eine Rückmeldung und einen Beleg oder eine Notiz angeben.')
            row.state = OutreachState(body.status)
            row.outcome_note = body.note
            row.outcome_at = now
            row.outcome_by = actor[:80]
        else:
            if body.status not in {'planned', 'done', 'closed'} or not body.note:
                raise ValueError('Bitte einen nächsten Schritt und eine Notiz eintragen.')
            if body.status == 'planned' and not body.due_date:
                raise ValueError('Bitte einen Termin für die Wiedervorlage wählen.')
            flow.setdefault('followups', {})[str(row.id)] = dict(status=body.status, note=body.note,
                due_date=body.due_date.isoformat() if body.due_date else None, actor=actor, updated_at=stamp)
    elif body.action in {'exclusive', 'exclusive_release', 'exclusive_extend'}:
        letters = list(session.scalars(select(Outreach).where(Outreach.client_id == workspace.client_id, Outreach.angle_id == workspace.angle_id)))
        if body.action == 'exclusive':
            if flow.get('sending'):
                raise ValueError('Ein Versand wurde bereits gestartet. Exklusivität kann nicht mehr geändert werden.')
            if any(r.released_at for r in letters):
                raise ValueError('Exklusivität muss vor dem ersten Versand festgelegt werden.')
            if body.text_id not in {r.id for r in letters}:
                raise ValueError('Bitte einen Pitch dieses Themas auswählen.')
            flow['exclusive'] = dict(text_id=body.text_id, until=None)
        else:
            exclusive = flow.get('exclusive', {})
            if not exclusive.get('text_id') or not exclusive.get('until'):
                raise ValueError('Die Exklusivphase hat noch nicht begonnen.')
            if body.action == 'exclusive_extend':
                exclusive['until'] = (max(now, dt.datetime.fromisoformat(exclusive['until'])) + dt.timedelta(hours=24)).isoformat()
            else:
                if dt.datetime.fromisoformat(exclusive['until']) > now:
                    raise ValueError('Die zugesagte Exklusivfrist läuft noch.')
                if not body.note:
                    raise ValueError('Bitte Rückmeldung prüfen und die Freigabe begründen.')
                exclusive['released_at'] = stamp
    elif body.action == 'pitch_plan':
        flow['master_pitch'] = body.note
    elif body.action == 'complete':
        if any(attempt.get('status') in {'sending','uncertain'} for attempt in flow.get('sending',{}).values()):
            raise ValueError('Bitte den offenen Versandstatus vor dem Abschluss mit Gmail abgleichen.')
        running = session.scalar(select(OpportunityAssetRun.id).where(OpportunityAssetRun.workspace_id == workspace.id,
            OpportunityAssetRun.status == 'running', OpportunityAssetRun.started_at > now - dt.timedelta(minutes=20)))
        if running:
            raise ValueError('RAUTE erstellt oder prüft noch einen Text. Bitte den Arbeitsschritt abwarten.')
        if not body.note:
            raise ValueError('Bitte das Ergebnis oder den Grund für den Abschluss festhalten.')
        flow.update(completed_at=stamp, completed_by=actor, result=body.note, review_date=body.due_date.isoformat() if body.due_date else None)
    elif body.action == 'reopen':
        flow.pop('completed_at', None)
        flow.pop('completed_by', None)
    data['workflow'] = flow
    workspace.data = data
    workspace.revision += 1
    session.add(OpportunityEvent(workspace_id=workspace.id, kind=f'topic_{body.action}', actor=actor,
        detail=dict(text_id=body.text_id, digest=body.digest, status=body.status, note=body.note, reviewer=body.reviewer,
                    due_date=body.due_date.isoformat() if body.due_date else None)))
