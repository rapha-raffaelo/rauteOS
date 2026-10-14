"""ein freigegebener Text lässt sich archivieren, aber nicht löschen

Die Asset-Liste wächst mit jedem Lauf, und irgendwann steht dort Arbeit vom
letzten Quartal zwischen der von heute. Es braucht also einen Weg, Dinge aus
der Liste zu nehmen — aber nicht denselben Weg für alles:

* Ein **Entwurf** hat nie jemand ausser uns gesehen. Er darf bearbeitet und
  gelöscht werden; ein Papierkorb ist hier wirklich ein Papierkorb.
* Ein **freigegebener** Text ist raus. Ihn zu löschen hiesse, nachträglich
  verschwinden zu lassen, was ein Kunde schon gesehen und freigegeben hat —
  und der Grundsatz "Released texts stay final" steht schon in assets_view.
  Er wird deshalb archiviert: aus der Liste genommen, in der Datenbank
  behalten, über seinen Link weiter erreichbar.

Eine Spalte und kein Status-Enum: "archiviert" ist kein Schritt in der
Bearbeitung eines Textes, sondern eine Aussage darüber, ob er noch in der
Liste stehen soll. Ein Zeitstempel sagt zusätzlich, wann — ein Boolean könnte
das nicht.

Revision ID: 0063_asset_archived
Revises: 0062_default_drafts
Create Date: 2026-10-13
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0063_asset_archived"
down_revision: str | None = "0062_default_drafts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("assets") as batch:
        # ``timezone=True`` wie jede Schwesterrevision; SQLite ignoriert es,
        # und ohne es meldet ein autogenerate-Abgleich auf einem anderen
        # Backend eine Abweichung.
        batch.add_column(sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("assets") as batch:
        batch.drop_column("archived_at")
