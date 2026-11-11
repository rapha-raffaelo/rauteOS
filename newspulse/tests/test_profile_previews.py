import json
from types import SimpleNamespace
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from newspulse.models import Base, Setting
from newspulse.profile_previews import previews, fingerprint, PREFIX


def test_preview_only_applies_to_the_unchanged_original():
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        row = SimpleNamespace(id=1, value='Original')
        session.add(Setting(key=PREFIX+'1', value=json.dumps({'hash':fingerprint(row.value),'text':'• Kurz'})))
        session.commit()
        assert previews(session, [row]) == {1:'• Kurz'}
        row.value = 'Neue Aussage'
        assert previews(session, [row]) == {}
