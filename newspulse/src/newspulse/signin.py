"""Erkennen, dass die Anmeldung des ``claude``-CLI abgelaufen ist.

Der 13. Oktober 2026, gemessen: vierzehn Läufe in Folge gescheitert, seit dem
30. September, 3154 Artikel unanalysiert, 685 davon aus den letzten sieben
Tagen. Gesehen hat es niemand — denn in der Kopfzeile stand

    11 Fehler im Nachrichtenlauf

mit dem Hinweis "Details im Log". Elf Fehler lesen sich wie elf Feed-Schluckaufe
an einem schlechten Morgen. Es war aber ein einziger Fehler, elfmal wiederholt,
und zwar derjenige, der jede modellgestützte Funktion des Werkzeugs zugleich
stilllegt: Analyse, Impulse, Chancen, Profilrecherche, Sichtbarkeitsmessung,
Captain Comms.

Dieses Modul macht aus elf Zeilen eine Aussage. Die Erkennung sitzt hier und
nicht in der Kopfzeile, weil zwei Seiten sie brauchen und weil "ist das die tote
Anmeldung?" eine Tatsachenfrage über einen Lauf ist, keine Darstellungsfrage.

Die Anmeldung läuft von sich aus ab — das ist kein Defekt, sondern die Natur
eines OAuth-Tokens. Was ein Defekt war: dass sie leise abläuft.
"""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from . import config

#: Was in einer Fehlerzeile steht, wenn das CLI sich nicht anmelden kann.
#:
#: Zwei Formulierungen statt einer, und beide müssen vorkommen können: Die erste
#: ist, was das CLI heute sagt; die zweite ist die allgemeinere Form, die es bei
#: einem fehlenden Token sagt. Eine dritte Zeile hier aufzunehmen ist billig, ein
#: übersehener Ausfall kostet zwei Wochen.
_MARKS: tuple[str, ...] = (
    "oauth session expired",
    "failed to authenticate",
    "please run /login",
    "invalid api key",
    "authentication_error",
)


def is_signin_failure(message: object) -> bool:
    """Ob diese eine Fehlerzeile von der Anmeldung handelt.

    Groß-/Kleinschreibung spielt keine Rolle: die Zeile wird aus der Ausgabe
    eines Unterprozesses zusammengesetzt, und deren Schreibweise ist nichts,
    worauf sich eine Alarmierung stützen sollte.
    """
    return any(mark in str(message or "").casefold() for mark in _MARKS)


def failed(errors: Iterable[object] | None) -> bool:
    """Ob in diesem Lauf die Anmeldung der Grund war.

    Eine einzige solche Zeile genügt. Der Lauf verarbeitet die Mandanten
    nacheinander, und ein abgelaufenes Token wird beim zweiten Mandanten nicht
    wieder gültig — wer hier eine Mehrheit verlangte, würde einen Lauf mit zehn
    Mandanten anders behandeln als einen mit zweien.
    """
    return any(is_signin_failure(line) for line in (errors or ()))


def affected(errors: Iterable[object] | None) -> int:
    """Wie viele Zeilen davon handeln. Für den Satz "betrifft 11 Mandanten"."""
    return sum(1 for line in (errors or ()) if is_signin_failure(line))


def other(errors: Iterable[object] | None) -> list[str]:
    """Die übrigen Fehler, also die, die wirklich verschieden sind.

    Die tote Anmeldung verdeckt sonst alles andere: ein kaputter Feed neben elf
    Anmeldezeilen geht in der Zahl unter, und genau dieser Feed bleibt dann auch
    nach dem Neuanmelden kaputt.
    """
    return [str(line) for line in (errors or ()) if not is_signin_failure(line)]


# --- Vorher warnen statt hinterher melden -----------------------------------------
#
# Der Teil oben erkennt den Ausfall, nachdem er eingetreten ist. Das ist besser
# als nichts, aber es ist immer noch zu spät: an dem Morgen, an dem die Meldung
# erscheint, wurde die Nacht schon nicht analysiert.
#
# Die Zugangsdatei weiss, wann sie stirbt. Sie trägt ``refreshTokenExpiresAt``,
# und im Fall vom Oktober 2026 stand dort der 23. September — sechs Tage vor dem
# ersten gescheiterten Lauf. RauteOS hätte es also sagen können, bevor etwas
# ausfiel, und tut es ab jetzt.
#
# **Gelesen wird ausschliesslich das Ablaufdatum.** Die Token selbst werden
# nicht angefasst, nicht zurückgegeben und nirgends protokolliert. Das ist der
# Grund, warum dieser Code hier steht und nicht in ``analyzer``: dessen
# Modulkopf verspricht ausdrücklich, die Datei nie zu lesen ("It NEVER reads an
# on-disk OAuth token"), und dieses Versprechen soll gelten bleiben. Ein
# Ablaufdatum ist kein Zugangsschlüssel.

#: Ab hier wird gewarnt. Eine Woche ist genug Zeit, um sich an einem ruhigen Tag
#: neu anzumelden, und kurz genug, dass die Warnung nicht zur Tapete wird.
WARN_WITHIN = dt.timedelta(days=7)


def _credentials_path() -> Path | None:
    """Wo die Zugangsdatei liegt, oder ``None`` wenn kein Ort konfiguriert ist.

    Ohne ``NEWSPULSE_CLAUDE_CONFIG_DIR`` läuft das CLI mit seinem eigenen
    Vorgabeort, und den zu erraten hiesse, auf einer fremden Maschine in einem
    Heimatverzeichnis zu suchen. Dann wird eben nicht gewarnt.
    """
    configured = (config.CLAUDE_CONFIG_DIR or "").strip()
    if not configured:
        return None
    return Path(configured).expanduser() / ".credentials.json"


def expires_at() -> dt.datetime | None:
    """Wann die Anmeldung endgültig abläuft, soweit die Datei es sagt.

    ``refreshTokenExpiresAt`` und nicht ``expiresAt``: das erste ist der Tag,
    an dem Schluss ist, das zweite nur die Frist des kurzlebigen Zugriffstokens,
    das sich bis dahin von selbst erneuert. Auf das kurze zu schauen hiesse,
    jeden zweiten Tag zu warnen.

    Jede Form von Unlesbarkeit ergibt ``None``: keine Datei, kaputtes JSON,
    fehlendes Feld, unsinniger Wert. Eine Warnung, die auf einer Vermutung
    beruht, ist schlimmer als keine — sie lehrt, Warnungen zu übergehen.
    """
    path = _credentials_path()
    if path is None or not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        stamp = raw["claudeAiOauth"]["refreshTokenExpiresAt"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if not isinstance(stamp, (int, float)) or stamp <= 0:
        return None
    # Millisekunden, wie das CLI sie schreibt. Die Grenze liegt weit jenseits
    # jedes plausiblen Sekundenwerts, damit beides erkannt wird, falls sich die
    # Einheit je ändert.
    seconds = stamp / 1000 if stamp > 1e11 else stamp
    try:
        return dt.datetime.fromtimestamp(seconds, dt.UTC)
    except (OverflowError, OSError, ValueError):
        return None


@dataclass(frozen=True, slots=True)
class Standing:
    """Wie es um die Anmeldung steht, für die Kopfzeile."""

    expires_at: dt.datetime | None
    days_left: int | None

    @property
    def known(self) -> bool:
        return self.expires_at is not None

    @property
    def expired(self) -> bool:
        return self.days_left is not None and self.days_left < 0

    @property
    def soon(self) -> bool:
        """Läuft bald ab, aber noch nicht abgelaufen."""
        return self.days_left is not None and 0 <= self.days_left <= WARN_WITHIN.days


def standing(*, now: dt.datetime | None = None) -> Standing:
    """Der Stand der Anmeldung, ohne das Netz zu befragen."""
    when = expires_at()
    if when is None:
        return Standing(expires_at=None, days_left=None)
    moment = now or dt.datetime.now(dt.UTC)
    return Standing(expires_at=when, days_left=(when - moment).days)
