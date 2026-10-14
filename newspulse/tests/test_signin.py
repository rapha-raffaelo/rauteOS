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


# --- Vorher warnen statt hinterher melden -------------------------------------------
#
# Die Erkennung oben meldet den Ausfall, nachdem er eingetreten ist. An dem
# Morgen, an dem die Meldung erscheint, wurde die Nacht schon nicht analysiert.
#
# Die Zugangsdatei weiss, wann sie stirbt: sie trägt ``refreshTokenExpiresAt``.
# Im Fall vom Oktober 2026 stand dort der 23. September — die Warnung wäre am
# 16. erschienen, der erste Ausfall war am 30. Vierzehn Tage Vorlauf statt zwei
# Wochen Stille.

import datetime as dt
import json


def _credentials(tmp_path, monkeypatch, *, expires: dt.datetime | None, **over):
    from newspulse import config

    payload = {
        "claudeAiOauth": {
            "accessToken": "GEHEIM-darf-nie-gelesen-werden",
            "refreshToken": "AUCH-GEHEIM",
            "expiresAt": 1,
            **({"refreshTokenExpiresAt": int(expires.timestamp() * 1000)} if expires else {}),
            **over,
        }
    }
    (tmp_path / ".credentials.json").write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(config, "CLAUDE_CONFIG_DIR", str(tmp_path))
    return payload


def test_the_expiry_is_read_from_the_file(tmp_path, monkeypatch):
    when = dt.datetime(2026, 9, 23, 20, 16, 25, tzinfo=dt.UTC)
    _credentials(tmp_path, monkeypatch, expires=when)

    assert signin.expires_at() == when


def test_the_real_production_credential_shape_is_understood(tmp_path, monkeypatch):
    """Der Prüfstein: genau der Wert, der am 13.10.2026 auf dem Server stand.
    Ändert das CLI das Feld oder die Einheit, fällt dieser Test — und das ist
    richtig, denn eine Warnung, die nicht mehr greift, ist schlimmer als keine."""
    _credentials(tmp_path, monkeypatch, expires=None,
                 refreshTokenExpiresAt=1790194585000)

    assert signin.expires_at() == dt.datetime(2026, 9, 23, 20, 16, 25, tzinfo=dt.UTC)


def test_it_warns_two_weeks_before_the_portfolio_went_dark(tmp_path, monkeypatch):
    """Der gemessene Fall, als Test. Am 16.09. hätte die Warnung gestanden."""
    _credentials(tmp_path, monkeypatch,
                 expires=dt.datetime(2026, 9, 23, 20, 16, tzinfo=dt.UTC))

    on_the_16th = signin.standing(now=dt.datetime(2026, 9, 16, 9, 0, tzinfo=dt.UTC))

    assert on_the_16th.soon, "sieben Tage vorher muss sie stehen"
    assert on_the_16th.days_left == 7
    assert not on_the_16th.expired


def test_it_stays_quiet_while_there_is_time(tmp_path, monkeypatch):
    """Eine Warnung, die immer dasteht, wird zur Tapete."""
    _credentials(tmp_path, monkeypatch,
                 expires=dt.datetime(2026, 12, 1, tzinfo=dt.UTC))

    quiet = signin.standing(now=dt.datetime(2026, 10, 14, tzinfo=dt.UTC))

    assert not quiet.soon
    assert not quiet.expired
    assert quiet.known


def test_an_expired_credential_is_not_merely_soon(tmp_path, monkeypatch):
    _credentials(tmp_path, monkeypatch,
                 expires=dt.datetime(2026, 9, 23, tzinfo=dt.UTC))

    late = signin.standing(now=dt.datetime(2026, 10, 13, tzinfo=dt.UTC))

    assert late.expired
    assert not late.soon, "abgelaufen ist kein Grad von 'bald'"


@pytest.mark.parametrize(
    "broken",
    [
        '{"claudeAiOauth": {}}',          # Feld fehlt
        '{"claudeAiOauth": {"refreshTokenExpiresAt": "bald"}}',
        '{"claudeAiOauth": {"refreshTokenExpiresAt": 0}}',
        "kein json",
        "",
    ],
)
def test_anything_unreadable_means_no_warning_rather_than_a_guess(
    tmp_path, monkeypatch, broken
):
    """Eine Warnung auf einer Vermutung ist schlimmer als keine — sie lehrt,
    Warnungen zu übergehen."""
    from newspulse import config

    (tmp_path / ".credentials.json").write_text(broken, encoding="utf-8")
    monkeypatch.setattr(config, "CLAUDE_CONFIG_DIR", str(tmp_path))

    assert signin.expires_at() is None
    assert not signin.standing().known


def test_without_a_configured_directory_nothing_is_guessed(monkeypatch):
    """Ohne NEWSPULSE_CLAUDE_CONFIG_DIR läuft das CLI mit seinem eigenen Ort,
    und den zu erraten hiesse, in einem fremden Heimatverzeichnis zu suchen."""
    from newspulse import config

    monkeypatch.setattr(config, "CLAUDE_CONFIG_DIR", "")

    assert signin.expires_at() is None


def test_the_tokens_themselves_are_never_returned(tmp_path, monkeypatch):
    """Die Grenze, die dieses Modul einhält: ``analyzer`` verspricht im
    Modulkopf, die Datei nie zu lesen ("It NEVER reads an on-disk OAuth token").
    Hier wird sie gelesen — aber nur das Ablaufdatum. Ein Datum ist kein
    Zugangsschlüssel."""
    _credentials(tmp_path, monkeypatch,
                 expires=dt.datetime(2026, 12, 1, tzinfo=dt.UTC))

    standing = signin.standing()

    assert "GEHEIM" not in repr(standing)
    assert "GEHEIM" not in str(signin.expires_at())
