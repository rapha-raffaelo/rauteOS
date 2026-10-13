"""Die abgelaufene Anmeldung erkennen und sie beim Namen nennen.

Am 13. Oktober 2026 gemessen: vierzehn Läufe in Folge gescheitert, seit dem
30. September, 3154 Artikel unanalysiert, 685 davon aus den letzten sieben
Tagen. In der Kopfzeile stand die ganze Zeit

    11 Fehler im Nachrichtenlauf        Details im Log

Elf Fehler lesen sich wie elf Feed-Schluckaufe an einem schlechten Morgen. Es
war ein einziger Fehler, elfmal wiederholt, und er legt jede modellgestützte
Funktion zugleich still. Diese Datei hält fest, dass er sich nie wieder als
Zahl tarnen kann.

Die Fehlerzeilen unten sind wörtlich die aus der Produktion.
"""

from __future__ import annotations

import pytest

from newspulse import signin

#: Wörtlich aus dem Lauf vom 13.10.2026.
_REAL = (
    "analysis 'Zalando': 25 batch(es) dropped: claude -p exited 1: "
    "Failed to authenticate: OAuth session expired and could not be refreshed"
)
_FEED = "feed 'Handelsblatt': timed out"


def test_the_real_production_line_is_recognised():
    """Der Prüfstein. Ändert sich der Wortlaut des CLI, fällt dieser Test — und
    das ist richtig so: lieber ein roter Test als zwei weitere stille Wochen."""
    assert signin.is_signin_failure(_REAL)


@pytest.mark.parametrize(
    "line",
    [
        "claude -p exited 1: Please run /login",
        "OAUTH SESSION EXPIRED",  # Schreibweise eines Unterprozesses ist kein Vertrag
        "authentication_error: invalid x-api-key",
        "Invalid API key · Fix external API key",
    ],
)
def test_the_other_shapes_of_a_dead_sign_in_are_recognised(line):
    assert signin.is_signin_failure(line)


@pytest.mark.parametrize(
    "line",
    [
        _FEED,
        "match: unexpected shape",
        "news APIs: HTTP 429: rate_limit_reached",
        "",
        None,
    ],
)
def test_an_ordinary_failure_is_not_mistaken_for_it(line):
    """Der teure Irrtum in die andere Richtung: ein Feed-Ausfall, der als tote
    Anmeldung gemeldet wird, schickt jemanden zum Neuanmelden statt zum Feed."""
    assert not signin.is_signin_failure(line)


def test_one_line_is_enough_to_call_the_run_dead():
    """Der Lauf arbeitet die Mandanten nacheinander ab, und ein abgelaufenes
    Token wird beim zweiten nicht wieder gültig. Wer eine Mehrheit verlangte,
    behandelte ein Portfolio mit zehn Mandanten anders als eines mit zweien."""
    assert signin.failed([_FEED, _REAL])
    assert not signin.failed([_FEED])
    assert not signin.failed([])
    assert not signin.failed(None)


def test_the_other_failures_are_kept_apart():
    """Sonst verdeckt der eine Ausfall jeden anderen: ein kaputter Feed neben
    elf Anmeldezeilen geht in der Zahl unter — und bleibt auch nach dem
    Neuanmelden kaputt, ohne dass es jemand gesehen hätte."""
    errors = [_REAL, _REAL, _FEED]

    assert signin.affected(errors) == 2
    assert signin.other(errors) == [_FEED]
