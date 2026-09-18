"""Create the default press-release draft as part of a new impulse's job.

Called by generation jobs only, never by a page GET. Existing drafts and releases
are retained. Missing facts or a model failure must not discard a valid impulse.
"""
import logging
from . import assets

_log = logging.getLogger(__name__)


def press_release(session, client, angle, *, note=None):
    try:
        return assets.produce(session, assets.definition('pressemitteilung'),
                              client, angle, only_if_missing=True, note=note)
    except Exception as exc:
        session.rollback()
        _log.warning('Default press release could not be completed: %s', exc)
        if note:
            note(f'Pressemitteilung noch nicht erstellt: {exc}')
        return None
