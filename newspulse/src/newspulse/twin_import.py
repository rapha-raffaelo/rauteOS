"""Bounded XLSX/CSV parsing. Only a reviewed preview may become live statements."""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import io
import itertools
import json
import uuid
import zipfile

import openpyxl
from pydantic import ValidationError
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from .models import ClientFact, TwinImportPreview
from .twin import CATALOG_BY_KEY, StatementInput, apply

MAX_BYTES = 5 * 1024 * 1024
MAX_ROWS = 2500
COLUMNS = {"key": "ID", "value": "Antwort / Input", "source_title": "Quelle / Dokument",
           "evidence_type": "Evidence Type", "source_type": "Source Type", "as_of": "Datum",
           "confidence": "Confidence", "confidentiality": "Vertraulichkeit", "external_use": "Externe Nutzung",
           "fact_status": "Status", "input_owner": "Input Owner", "note": "Notizen", "source_url": "Source URL"}


def _tables(data: bytes, filename: str):
    if len(data) > MAX_BYTES:
        raise ValueError("Datei ist größer als 5 MB.")
    if filename.lower().endswith('.csv'):
        try:
            text = data.decode('utf-8-sig')
            dialect = csv.Sniffer().sniff(text[:8192], delimiters=',;\t')
        except (UnicodeDecodeError, csv.Error):
            raise ValueError("CSV bitte als UTF-8 mit Kopfzeile exportieren.") from None
        yield 'CSV', list(itertools.islice(csv.reader(io.StringIO(text), dialect), MAX_ROWS + 2))
    elif filename.lower().endswith('.xlsx'):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                if sum(f.file_size for f in archive.infolist()) > 30 * 1024 * 1024:
                    raise ValueError("Entpackte Arbeitsmappe ist zu groß.")
            book = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=False, keep_links=False)
            try:
                for sheet in book:
                    if sheet.title.startswith(('00_', '05_', '99_')):
                        continue
                    rows = []
                    for row in sheet.iter_rows(values_only=True, max_col=64):
                        rows.append(row)
                        if len(rows) > MAX_ROWS + 1:
                            raise ValueError("Zu viele Zeilen in der Arbeitsmappe.")
                    yield sheet.title, rows
            finally:
                book.close()
        except (zipfile.BadZipFile, KeyError, OSError):
            raise ValueError("Keine lesbare XLSX-Datei.") from None
    else:
        raise ValueError("Bitte eine XLSX- oder CSV-Datei wählen.")


def preview(session: Session, client_id: int, data: bytes, filename: str, mapping: dict[str, str]) -> dict:
    if any(key not in COLUMNS for key in mapping):
        raise ValueError("Unbekannte Spaltenzuordnung.")
    if any(not isinstance(value, str) for value in mapping.values()):
        raise ValueError("Spaltennamen müssen Text sein.")
    selected = COLUMNS | mapping
    columns = []
    results = []
    for sheet, table in _tables(data, filename):
        if not table:
            continue
        headers = [str(cell or '').strip() for cell in table[0]]
        columns += [h for h in headers if h and h not in columns]
        if len(table) > MAX_ROWS + 1 or len(results) + len(table) > MAX_ROWS + 1:
            raise ValueError("Zu viele Zeilen im Import.")
        if selected['key'] not in headers or selected['value'] not in headers:
            results.append(dict(index=len(results), sheet=sheet, line=1, state='error',
                                message='Spalten für ID und Antwort zuordnen.', data=None))
            continue
        used = [v for v in selected.values() if v]
        if any(headers.count(name) > 1 for name in used):
            raise ValueError("Doppelte Spaltennamen bitte in der Datei eindeutig benennen.")
        for line, cells in enumerate(table[1:], start=2):
            raw = {key: cells[headers.index(header)] for key, header in selected.items()
                   if header in headers and headers.index(header) < len(cells)}
            if not any(c is not None and str(c).strip() for c in cells):
                continue
            result = dict(index=len(results), sheet=sheet, line=line, state='ready', message='', data=None)
            if raw.get('value') is None or not str(raw['value']).strip():
                result.update(state='empty', message='Keine Antwort – wird nicht importiert.')
            else:
                try:
                    values = {}
                    for key, value in raw.items():
                        if value is None or str(value).strip() == '':
                            continue
                        if isinstance(value, str) and value.lstrip().startswith('='):
                            raise ValueError('Formeln bitte als Werte exportieren.')
                        if key == 'as_of':
                            if isinstance(value, dt.datetime): value = value.date()
                            elif isinstance(value, str):
                                try: value = dt.date.fromisoformat(value.strip())
                                except ValueError: value = dt.datetime.strptime(value.strip(), '%d.%m.%Y').date()
                        else:
                            value = str(value).strip()
                        values[key] = value
                    field = CATALOG_BY_KEY.get(values.get('key'), {})
                    values.setdefault('input_owner', field.get('input_owner', 'RAUTE'))
                    if 'evidence_type' not in values:
                        key = values.get('key', '')
                        values['evidence_type'] = ('RAUTE Hypothesis' if key.startswith('C') else
                                                  'External Observation' if key.startswith('D') else 'Client Statement')
                        result['message'] = 'Herkunft nicht ausgefüllt; vorläufige Einordnung aus dem Fragebogen-Bereich prüfen.'
                    values.setdefault('source_title', filename[:200])
                    statement = StatementInput.model_validate(values)
                    result['data'] = statement.model_dump(mode='json')
                    # A spreadsheet's Fact label is not an independent review.
                    if statement.evidence_type == 'Fact':
                        result['message'] = 'Als Fact bezeichnet; unabhängige Bestätigung im Twin steht noch aus.'
                except ValidationError as exc:
                    result.update(state='error', message='; '.join(
                        f"{e['loc'][0]}: {e['msg']}" for e in exc.errors(include_input=False)))
                except (ValueError, TypeError):
                    result.update(state='error', message='Ungültiges Datum oder Formel. Datum: YYYY-MM-DD oder DD.MM.YYYY.')
            results.append(result)
    # Dedup compares the original reviewed input, not a later hand-edited value.
    existing = set(session.scalars(select(ClientFact.import_hash).where(ClientFact.client_id == client_id)))
    seen = set()
    for row in results:
        if row['state'] != 'ready': continue
        fingerprint = hashlib.sha256(json.dumps(row['data'], sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        row['fingerprint'] = fingerprint
        if fingerprint in existing or fingerprint in seen:
            row.update(state='duplicate', message='Bereits importiert oder doppelt in dieser Datei.')
        seen.add(fingerprint)
    now = dt.datetime.now(dt.UTC)
    session.execute(delete(TwinImportPreview).where(TwinImportPreview.expires_at < now))
    payload = dict(columns=columns, mapping=selected, rows=results)
    record = TwinImportPreview(id=str(uuid.uuid4()), client_id=client_id, created_at=now,
                              expires_at=now + dt.timedelta(hours=1), payload=payload)
    session.add(record)
    session.commit()
    return dict(id=record.id, **payload)


def commit(session: Session, client_id: int, preview_id: str, selected: list[int], person: str) -> dict:
    record = session.get(TwinImportPreview, preview_id)
    now = dt.datetime.now(dt.UTC)
    if record is None or record.client_id != client_id:
        raise LookupError('Importvorschau nicht gefunden.')
    if record.expires_at < now:
        raise ValueError('Vorschau ist abgelaufen. Datei erneut prüfen.')
    if record.committed_at:
        return dict(created=0, skipped=len(selected), already_committed=True)
    if record.payload.get('kind') == 'ai-job':
        raise ValueError('Zunächst die Antwortvorschläge prüfen.')
    rows = {r['index']: r for r in record.payload['rows']}
    if not selected or any(i not in rows or rows[i]['state'] != 'ready' for i in selected):
        raise ValueError('Nur gültige, ausgewählte Aussagen können importiert werden.')
    # Claim this preview in the same transaction as its rows: retries are idempotent.
    changed = session.execute(update(TwinImportPreview).where(
        TwinImportPreview.id == preview_id, TwinImportPreview.committed_at.is_(None)
    ).values(committed_at=now)).rowcount
    if not changed:
        return dict(created=0, skipped=len(selected), already_committed=True)
    existing = set(session.scalars(select(ClientFact.import_hash).where(ClientFact.client_id == client_id)))
    ai_import = record.payload.get('kind') == 'ai'
    occupied = set(session.scalars(select(ClientFact.key).where(ClientFact.client_id == client_id,
        (ClientFact.fact_status.is_(None) | ClientFact.fact_status.notin_(['Rejected', 'Archived']))))) if ai_import else set()
    created = skipped = 0
    for index in dict.fromkeys(selected):
        item = rows[index]
        if item['fingerprint'] in existing or (ai_import and item['data']['key'] in occupied):
            skipped += 1
            continue
        row = apply(session, client_id, StatementInput.model_validate(item['data']), person)
        row.import_hash = item['fingerprint']
        if ai_import:
            row.filled_by = 'ki'
            occupied.add(row.key)
        session.flush()
        existing.add(item['fingerprint'])
        created += 1
    # Drop staged client answers after use; the statements and history retain them.
    record.payload = {}
    session.commit()
    return dict(created=created, skipped=skipped, already_committed=False)
