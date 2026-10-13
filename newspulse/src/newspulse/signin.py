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

from collections.abc import Iterable

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
