"""Queue the missing default draft without delaying new-impulse generation."""
import logging
from . import default_drafts
_log = logging.getLogger(__name__)


def press_release(session, client, angle, *, note=None):
    try:
        return default_drafts.enqueue(session, client, angle)
    except Exception:
        session.rollback()
        _log.exception('Default draft could not be queued')
        if note:
            note('Die Pressemitteilung konnte noch nicht eingeplant werden.')
        return None
