import io
import openpyxl
from pypdf import PdfReader, PdfWriter
from sqlalchemy import select
from test_twin import db, web, upload
from newspulse import twin
from newspulse.models import ClientFact


def test_excel_download_filled_upload_and_selected_commit(web, db):
    download = web.get('/api/v1/clients/1/twin/questionnaire/xlsx')
    assert download.status_code == 200
    assert 'attachment' in download.headers['content-disposition']
    book = openpyxl.load_workbook(io.BytesIO(download.content))
    sheet = book['Fragebogen']
    assert sheet['A2'].value == 'A01.01'
    assert sheet.max_row == len(twin.fields()) + 1
    sheet['E2'] = 'Beispiel GmbH'
    sheet['F2'] = 'Ausgefüllter Fragebogen'
    out = io.BytesIO(); book.save(out)
    result = upload(web, out.getvalue()).json()
    assert result['rows'][0]['data']['value'] == 'Beispiel GmbH'
    assert all(r['state'] == 'empty' for r in result['rows'][1:])
    assert not db.scalars(select(ClientFact)).all()
    saved = web.post('/api/v1/clients/1/twin/import/commit', json={'preview_id':result['id'],'selected':[0]})
    assert saved.status_code == 200 and saved.json()['created'] == 1
    assert db.scalar(select(ClientFact)).value == 'Beispiel GmbH'


def test_fillable_pdf_roundtrip_and_layout_bounds(web, db):
    download = web.get('/api/v1/clients/1/twin/questionnaire/pdf')
    assert download.status_code == 200 and len(download.content) < 5*1024*1024
    reader = PdfReader(io.BytesIO(download.content))
    assert len(reader.get_fields()) == len(twin.fields())*4
    for page in reader.pages:
        for ref in page.get('/Annots', []):
            assert ref.get_object()['/Rect'][1] > 24
    writer = PdfWriter(clone_from=reader)
    writer.update_page_form_field_values(writer.pages[0], {'answer__A01.01':'Müller & Söhne GmbH', 'source__A01.01':'Handelsregister', 'url__A01.01':'https://example.org/register'}, auto_regenerate=False)
    out = io.BytesIO(); writer.write(out)
    result = upload(web, out.getvalue(), 'ausgefüllt.pdf')
    assert result.status_code == 200, result.text
    row = result.json()['rows'][0]
    assert row['state'] == 'ready'
    assert row['data']['value'] == 'Müller & Söhne GmbH'
    assert row['data']['source_title'] == 'Handelsregister'
    assert row['data']['source_url'] == 'https://example.org/register'
    assert not db.scalars(select(ClientFact)).all()


def test_download_scope_and_unreadable_pdf_errors(web):
    assert web.get('/api/v1/clients/999/twin/questionnaire/xlsx').status_code == 404
    assert web.get('/api/v1/clients/3/twin/questionnaire/pdf').status_code == 404
    assert web.get('/api/v1/clients/1/twin/questionnaire/exe').status_code == 404
    out = io.BytesIO(); writer = PdfWriter(); writer.add_blank_page(width=600, height=800);writer.write(out)
    result = upload(web,out.getvalue(),'scan.pdf')
    assert result.status_code == 422 and 'Antwortfelder' in result.json()['detail']
    assert upload(web,b'not a pdf','bad.pdf').status_code == 422
