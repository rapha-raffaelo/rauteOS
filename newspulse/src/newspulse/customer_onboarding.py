"""Five-minute CEO interview and a sourced, public company snapshot."""
import datetime as dt
from urllib.parse import urlsplit
from sqlalchemy import select
from . import profile, twin
from .evidence import Confidentiality, FactStatus, SourceType
from .models import ClientFact

QUESTION_KEYS = ('B01.01', 'B03.01', 'B03.04', 'B04.03', 'B07.11')
LABELS = {
    'B01.01': 'Wo möchten Sie in drei Jahren stehen?',
    'B03.01': 'Wofür möchten Sie bekannt sein?',
    'B03.04': 'Wie mutig dürfen wir Sie positionieren?',
    'B04.03': 'Welche Branchenmeinung halten Sie für falsch?',
    'B07.11': 'Welche Pläne müssen vorerst vertraulich bleiben?',
}
HINTS = {
    'B01.01': 'Ihr wichtigstes Ziel genügt. Ein Satz oder eine kurze Sprachantwort.',
    'B03.01': 'Tippen Sie passende Begriffe an. Eigene Worte sind genauso willkommen.',
    'B03.04': 'Wählen Sie die Richtung, die zu Ihnen passt.',
    'B04.03': 'Was sehen Sie anders als der Rest? Eine These reicht.',
    'B07.11': 'Zum Beispiel eine Übernahme, ein Produktstart oder ein neuer Markt. Nur das, was Sie teilen möchten.',
}
CHOICES = {
    'B03.01': ['Differenzierung', 'Premium', 'Technologieführerschaft', 'Challenger', 'Thought Leader', 'Neue Kategorie'],
    'B03.04': ['Zurückhaltend', 'Klar und selbstbewusst', 'Mutig und herausfordernd'],
    'B07.11': ['Aktuell keine vertraulichen Pläne', 'Besprechen wir persönlich'],
}


def questions():
    return [dict(key=key, text=LABELS[key], original_text=twin.CATALOG_BY_KEY[key]['label'],
                 help=HINTS[key], section='Ihre Perspektive · ca. 5 Minuten',
                 choices=CHOICES.get(key, []), single_choice=key in {'B03.04', 'B07.11'})
            for key in QUESTION_KEYS]


def web_source(url):
    return bool(url and urlsplit(url).scheme in {'http', 'https'} and urlsplit(url).netloc)


# Researchable public profile fields only. CEO intentions and agency hypotheses
# can never become customer prefills, even when they happen to carry a URL.
PUBLIC_KEYS = {f.key for f in profile.RESEARCHED}
CATALOG_KEYS = {f['legacy_key']: f['key'] for f in twin.CATALOG if f['legacy_key'] in PUBLIC_KEYS}
PUBLIC_SOURCES = {SourceType.WEBSITE, SourceType.MEDIA, SourceType.EXTERNAL_RESEARCH,
                  SourceType.STUDY, SourceType.PUBLIC_DATABASE}


def prepare(session, client, *, research=True):
    """Prepare before handing over a link; a customer GET never runs research.

    Fresh grounded research supplements explicitly public stored evidence. If the
    provider fails, sourced cached evidence can still support the preview, with
    its date and the failure visible to the agency. Never expose confidential rows.
    """
    public = {}
    for row in session.scalars(select(ClientFact).where(ClientFact.client_id == client.id)
                              .order_by(ClientFact.updated_at, ClientFact.id)):
        field = twin.CATALOG_BY_KEY.get(row.key)
        legacy = field.get('legacy_key') if field else row.key
        if ((legacy in PUBLIC_KEYS or field and row.key.startswith('A')) and row.confidentiality == Confidentiality.PUBLIC
                and row.source_type in PUBLIC_SOURCES and web_source(row.source_url)
                and row.fact_status not in {FactStatus.ARCHIVED, FactStatus.REJECTED, FactStatus.CONTRADICTORY, FactStatus.OUTDATED}
                and not row.is_disputed):
            public[legacy or row.key] = dict(key=row.key, label=profile.FIELDS_BY_KEY[legacy].label if legacy in PUBLIC_KEYS else field['label'],
                value=row.value, source_url=row.source_url, source_title=row.source_title,
                researched_at=row.updated_at.isoformat(), fact_id=row.id)
    # Proposals are not assumed safe for sharing: new public research provides
    # the external snapshot, while internal review notes stay in the dashboard.
    warning = ''
    try:
        found = profile.research(client) if research else []
    except Exception:
        found = []
        warning = 'Die neue Webrecherche ist fehlgeschlagen. Der Link verwendet nur vorhandene öffentliche Quellen mit Datum.'
    now = dt.datetime.now(dt.UTC).isoformat()
    for proposal in found:
        if proposal.key not in PUBLIC_KEYS or not web_source(proposal.source_url) or not proposal.value.strip():
            continue
        key = CATALOG_KEYS.get(proposal.key, proposal.key)
        # Unchanged researched statements are reused. Existing customer/agency
        # knowledge is never overwritten by the public preparation.
        existing = session.scalar(select(ClientFact).where(ClientFact.client_id == client.id,
            ClientFact.key == key, ClientFact.value == proposal.value,
            ClientFact.source_url == proposal.source_url,
            ClientFact.confidentiality == Confidentiality.PUBLIC,
            ClientFact.source_type == SourceType.WEBSITE,
            ClientFact.fact_status == FactStatus.NEEDS_VERIFICATION))
        if existing is None:
            existing = twin.apply(session, client.id, twin.StatementInput(key=key,
                value=proposal.value, source_url=proposal.source_url, source_title=proposal.source_title,
                source_type=SourceType.WEBSITE, confidentiality=Confidentiality.PUBLIC), 'Webrecherche · Onboarding')
            existing.filled_by = 'recherche'
        public[proposal.key] = dict(key=key, label=profile.FIELDS_BY_KEY[proposal.key].label,
            value=proposal.value, source_url=proposal.source_url, source_title=proposal.source_title,
            researched_at=now, fact_id=existing.id)
    if not public:
        raise ValueError('Noch keine belegten öffentlichen Angaben vorhanden. Bitte Website und Recherche-Zugang prüfen und die Vorbereitung erneut starten. Es wurde kein Kundenlink erstellt.')
    missing = [f.label for f in profile.RESEARCHED if f.key not in public]
    ordered = [public[f.key] for f in profile.RESEARCHED if f.key in public]
    ordered.extend(item for key, item in public.items() if key not in PUBLIC_KEYS)
    return ordered, warning, missing
