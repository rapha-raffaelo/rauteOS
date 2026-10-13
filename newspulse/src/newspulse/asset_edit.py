"""Einen erzeugten Text ändern, löschen oder archivieren.

Die Asset-Liste wächst mit jedem Lauf, und irgendwann steht Arbeit vom letzten
Quartal zwischen der von heute. Es braucht also einen Weg, Dinge herauszunehmen
— aber nicht denselben Weg für alles. Die Grenze verläuft an der Freigabe:

* Ein **Entwurf** hat nie jemand ausser uns gesehen. Er darf bearbeitet und
  gelöscht werden; hier ist ein Papierkorb wirklich ein Papierkorb.
* Ein **freigegebener** Text ist raus. Ihn zu ändern hiesse, nachträglich
  umzuschreiben, was ein Kunde gesehen und freigegeben hat; ihn zu löschen
  hiesse, es verschwinden zu lassen. Beides ist keine Aufräumarbeit, sondern
  das Verfälschen einer Akte. Er wird archiviert: aus der Liste genommen, in
  der Datenbank behalten, über seinen Link weiter erreichbar.

Diese Regel steht hier und nicht in der Route, weil sie eine Tatsache über
Texte ist und nicht über HTTP — und weil die Route sie sonst beim nächsten
Endpunkt noch einmal formulieren müsste, leicht anders.

``assets_view`` sagt dasselbe seit je in Worten ("Released texts stay final").
Dieses Modul macht daraus etwas, das man aufrufen kann.
"""

from __future__ import annotations

import datetime as dt
import logging

from sqlalchemy.orm import Session

from .models import Asset

_log = logging.getLogger(__name__)


class Refused(Exception):
    """Die Handlung ist für diesen Text nicht erlaubt. Trägt den Grund im Text."""


def is_draft(asset: Asset) -> bool:
    """Ob der Text noch keiner ausser uns gesehen hat."""
    return asset.released_at is None


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def edit(session: Session, asset: Asset, *, title: str, body: str) -> Asset:
    """Titel und Text eines Entwurfs ändern.

    ``edited_at`` wird gesetzt, weil die Seite zwischen "erzeugt" und "von Hand
    überarbeitet" unterscheidet: ein Text, an dem jemand gearbeitet hat, ist
    etwas anderes als einer, den das Werkzeug hingelegt hat.

    Ein leerer Rumpf wird abgelehnt statt gespeichert. Ein Text ohne Inhalt ist
    kein Text, und wer ihn loswerden will, hat dafür den Papierkorb.
    """
    if not is_draft(asset):
        raise Refused(
            "Freigegebene Texte lassen sich nicht mehr ändern. "
            "Was freigegeben wurde, hat der Kunde so gesehen."
        )
    cleaned = (body or "").strip()
    if not cleaned:
        raise Refused("Ohne Text lässt sich nichts speichern.")
    asset.title = (title or "").strip()
    asset.body = cleaned
    asset.edited_at = _now()
    session.commit()
    return asset


def delete(session: Session, asset: Asset) -> None:
    """Einen Entwurf löschen. Endgültig, und nur einen Entwurf."""
    if not is_draft(asset):
        raise Refused(
            "Freigegebene Texte lassen sich nicht löschen, nur archivieren. "
            "Sonst verschwindet nachträglich, was ein Kunde schon gesehen hat."
        )
    _log.info("Entwurf %d gelöscht (%r)", asset.id, (asset.title or "")[:60])
    session.delete(asset)
    session.commit()


def archive(session: Session, asset: Asset) -> Asset:
    """Einen Text aus der Liste nehmen, ohne ihn zu verlieren.

    Für freigegebene Texte der einzige Weg, und für Entwürfe ausdrücklich auch
    einer: nicht jeder verworfene Entwurf soll gelöscht werden müssen, nur weil
    er gelöscht werden *dürfte*.

    Zweimal archivieren ändert den Zeitstempel nicht. Das erste Mal ist die
    Handlung; ein zweiter Klick auf eine veraltete Liste darf nicht so
    aussehen, als wäre heute etwas geschehen.
    """
    if asset.archived_at is None:
        asset.archived_at = _now()
        session.commit()
    return asset


def restore(session: Session, asset: Asset) -> Asset:
    """Zurück in die Liste. Ohne diesen Weg wäre Archivieren ein Löschen mit
    besserem Namen."""
    if asset.archived_at is not None:
        asset.archived_at = None
        session.commit()
    return asset
