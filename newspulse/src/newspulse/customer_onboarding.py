"""The customer questionnaire and the researched company picture it opens with."""
from urllib.parse import urlsplit
from sqlalchemy import select
from . import onboarding_crawler, twin
from .evidence import Confidentiality, FactStatus, SourceType
from .models import ClientFact

# Every question is optional: the customer may skip any of them and finish
# with gaps, which the agency then sees as open rather than as answered.
QUESTION_KEYS = tuple(f['key'] for f in twin.CATALOG if f['key'].startswith('Q'))
SECTION = 'Unternehmensidentität und Strategie'
HINTS = {
    'Q01.01': "Welche persönlichen Erfahrungen, besonderen Herausforderungen, überraschenden Entwicklungen oder mutigen Entscheidungen stecken hinter der Entstehung und Entwicklung Ihres Unternehmens? Gab es entscheidende Momente, Rückschläge, Zufälle oder Veränderungen, die für Ihren heutigen Erfolg besonders wichtig waren, in der öffentlichen Darstellung aber bisher kaum eine Rolle spielen? Welche Hintergründe und Geschichten sollte man kennen, um Ihr Unternehmen wirklich zu verstehen?",
    'Q01.02': "Bitte nennen Sie nach Möglichkeit auch, woran Sie erkennen würden, dass jedes Ziel erreicht wurde.",
    'Q01.03': "Die öffentlich verfügbaren Informationen zu Ihren Angeboten haben wir bereits recherchiert. Uns interessiert vor allem, was darüber hinaus wichtig ist: Wie laufen die Nutzung Ihrer Produkte beziehungsweise die Erbringung Ihrer Dienstleistungen konkret ab? Welche Technologien, Methoden, Arbeitsschritte oder besonderen Kompetenzen kommen dabei zum Einsatz? Was ist für Außenstehende häufig schwer zu verstehen, welche Herausforderungen bestehen in der Praxis und welche Details sind entscheidend, um Ihr Angebot wirklich nachvollziehen zu können?",
    'Q01.04': "Wie gehen Ihre Kunden heute ohne Ihr Angebot vor? Welche Schwierigkeiten, Kosten oder Einschränkungen entstehen dabei? Was verändert sich durch den Einsatz Ihres Produkts beziehungsweise die Inanspruchnahme Ihrer Dienstleistung?",
    'Q01.05': "Welche Vorteile ergeben sich beispielsweise aus Technologie, Qualität, Fachkompetenz, Methodik, Geschwindigkeit, Ergebnissen, Wirtschaftlichkeit oder Kundenbetreuung? Welche dieser Vorteile sind belegbar oder für Wettbewerber schwer zu kopieren? Und in welchen Punkten sind andere Anbieter oder Lösungen gegebenenfalls stärker?",
    'Q01.06': "Bitte nennen Sie den jeweiligen Entwicklungs- beziehungsweise Planungsstand, den voraussichtlichen Zeitpunkt, die strategische Bedeutung und – soweit bereits erkennbar – das Kundenproblem, das Sie damit adressieren möchten.",
    'Q01.07': "Über die öffentlich verfügbaren Unternehmenskennzahlen hinaus interessieren uns insbesondere aktuelle Zahlen, Entwicklungen und Meilensteine, die Ihr Unternehmen und seine Leistungsfähigkeit greifbar machen. Welche Kennzahlen zeigen beispielsweise Wachstum, Nachfrage, Marktpräsenz, Kundenentwicklung oder die Wirkung Ihrer Produkte und Dienstleistungen? Welche Entwicklungen sind besonders bemerkenswert? Bitte geben Sie nach Möglichkeit den jeweiligen Zeitraum an und kennzeichnen Sie, welche Informationen öffentlich verwendet werden dürfen.",
    'Q01.08': "Bitte unterscheiden Sie – soweit relevant – zwischen den Personen, die Ihre Produkte nutzen beziehungsweise Ihre Dienstleistungen in Anspruch nehmen, fachlichen Entscheidern, Budgetverantwortlichen, Einkauf, Management, internen Fürsprechern und weiteren Personen, die eine Kauf- oder Beauftragungsentscheidung beeinflussen oder verhindern können.",
    'Q01.09': "Über welche Kanäle entstehen neue Geschäftsmöglichkeiten? Welche Schritte durchläuft eine Entscheidung, wie lange dauert sie typischerweise und welche Rolle spielen Vertrieb, persönliche Beziehungen, Partner, Ausschreibungen, Empfehlungen oder digitale Kanäle?",
    'Q01.10': "Welche Gründe sind ausschlaggebend dafür, dass Interessenten Ihre Produkte kaufen beziehungsweise Ihre Dienstleistungen beauftragen – oder sich letztlich dagegen entscheiden? Welche Rolle spielen beispielsweise Preis, Vertrauen, Qualität, Leistungsumfang, Wettbewerb oder interne Entscheidungsprozesse auf Kundenseite? Können Sie konkrete Beispiele für gewonnene und verlorene Aufträge nennen?",
    'Q01.11': "Aus welchen Gründen beenden Kunden die Zusammenarbeit, kündigen Verträge, beauftragen Sie nicht erneut oder wechseln zu Wettbewerbern? Welche Rolle spielen dabei beispielsweise Preis, Qualität, Ergebnisse, Kundenbetreuung, veränderte Anforderungen oder wirtschaftliche Entwicklungen auf Kundenseite? Gibt es wiederkehrende Muster, und was unternehmen Sie, um Kunden langfristig zu halten?",
    'Q01.12': "In welchen Märkten und Kundensegmenten sind Sie besonders stark vertreten und welche Rolle nehmen Sie dort ein? Wie bewerten Sie Ihre Marktposition im Vergleich zu anderen Anbietern? Wo sehen Sie Ihre größten Stärken, wo bestehen Nachteile und in welchen Bereichen möchten Sie Ihre Position künftig ausbauen? Gibt es Besonderheiten der Marktstruktur oder Wettbewerbsdynamik, die von außen nur schwer erkennbar sind?",
    'Q01.13': "Welche Veränderungen zeichnen sich aus Ihrer Marktkenntnis bereits ab, die für Außenstehende noch kaum erkennbar sind? An welchen neuen Technologien, Produkten, Dienstleistungen oder Geschäftsmodellen arbeiten Wettbewerber oder andere Marktteilnehmer aus Ihrer Sicht? Welche neuen Anbieter, Forschungsansätze, Partnerschaften oder Veränderungen im Kundenverhalten könnten die bisherigen Marktverhältnisse verschieben? Welche dieser Entwicklungen halten Sie für besonders relevant und welche Chancen oder Risiken ergeben sich daraus für Ihr Unternehmen?",
    'Q01.14': "Bitte nennen Sie beispielsweise strategische Partner, Lieferanten, Technologieplattformen, Vertriebspartner, spezialisierte Dienstleister, Subunternehmer, Branchenverbände, Behörden, Regulatoren oder andere Akteure mit erheblichem Einfluss auf Ihre Produkte, Ihre Leistungserbringung oder Ihren Markterfolg.",
    'Q01.15': "Welche Ausgangssituation bestand beim Kunden, welches Produkt wurde eingesetzt beziehungsweise welche Dienstleistung erbracht und welche Ergebnisse wurden erzielt? Welche Kundenreferenzen dürfen genannt werden und für welche Ergebnisse liegen belastbare Daten, Freigaben oder andere Belege vor?",
    'Q01.16': "Welche Produkte, Dienstleistungen, Kundengruppen, Märkte oder Initiativen entwickeln sich positiv? Was hat Sie daran gegebenenfalls überrascht und wodurch erklären Sie diese Entwicklung?",
    'Q01.17': "Bitte betrachten Sie ausdrücklich nicht nur Kommunikation: Welche Probleme beeinträchtigen Nachfrage, Vertrieb, Wachstum, Profitabilität, Expansion, Produktentwicklung, Dienstleistungsqualität, Leistungserbringung oder Wettbewerbsfähigkeit? Was haben Sie bisher dagegen unternommen?",
    'Q01.18': "Welche Kundengruppen, Märkte, Produkte, Dienstleistungen oder neuen Geschäftsfelder könnten relevant werden? Was hindert Sie bislang daran, diese Potenziale zu erschließen, und welche strategischen Entscheidungen beziehungsweise Zielkonflikte sind damit verbunden?",
    'Q01.19': "Dazu können beispielsweise regulatorische Beschränkungen, Genehmigungen, Schutzrechte, laufende Streitigkeiten, Produkt- oder Dienstleistungsqualität, Haftungsfragen, Cybervorfälle, Lieferkettenrisiken, Kapazitätsengpässe, sensible Personalthemen oder kritische öffentliche Debatten zählen.",
    'Q01.20': "Bei welchen Themen, Entwicklungen oder verbreiteten Überzeugungen widersprechen Sie der vorherrschenden Meinung? Was wird aus Ihrer Sicht in Ihrer Branche häufig falsch eingeschätzt oder übersehen? Welche eigenen Erfahrungen, Beobachtungen oder Daten haben Sie zu dieser Einschätzung gebracht?",
    'Q01.21': "Denken Sie beispielsweise an ungewöhnliche Kundenreaktionen, unerwartete Einsatzmöglichkeiten Ihrer Produkte, besondere Erfahrungen bei der Erbringung Ihrer Dienstleistungen, außergewöhnliche Kundenprojekte, Fehlentscheidungen, Wendepunkte, gescheiterte Versuche oder Situationen hinter den Kulissen, die auf Präsentationsfolien normalerweise nicht auftauchen.",
    'Q01.22': "Ihr Unternehmen steht mit verschiedenen Stakeholdergruppen in Verbindung – beispielsweise Kunden, potenziellen Kunden, Mitarbeitenden, Bewerbern, Geschäftspartnern, Investoren oder der Öffentlichkeit. Wie schätzen Sie die aktuelle Wahrnehmung Ihres Unternehmens bei diesen Gruppen jeweils ein? Gibt es dabei deutliche Unterschiede, Missverständnisse oder Vorstellungen, die aus Ihrer Sicht nicht der Realität entsprechen? Haben Sie bereits konkrete Überlegungen, bei welchen Stakeholdergruppen sich die Wahrnehmung verändern sollte, in welche Richtung und welche Ihrer Unternehmensziele Sie damit unterstützen möchten?",
}
# Unannounced plans and known risks stay internal; every other answer
# already needs approval before it is used outside the agency.
RESTRICTED = {'Q01.06', 'Q01.19'}


def questions():
    return [dict(key=key, text=twin.CATALOG_BY_KEY[key]['label'], help=HINTS[key],
                 section=SECTION, choices=[], single_choice=False)
            for key in QUESTION_KEYS]


def answered(answers):
    """Saved answers to the current questions; a renewed link may still carry older keys."""
    return sum(bool(answers.get(key, {}).get('value') or answers.get(key, {}).get('audio_id'))
               for key in QUESTION_KEYS)


def web_source(url):
    return bool(url and urlsplit(url).scheme in {'http', 'https'} and urlsplit(url).netloc)


# Researched topics only. Customer answers and agency hypotheses can never
# become customer prefills, even when they happen to carry a URL.
TOPIC_KEYS = tuple(onboarding_crawler.TOPICS)
PUBLIC_SOURCES = {SourceType.WEBSITE, SourceType.MEDIA, SourceType.EXTERNAL_RESEARCH,
                  SourceType.STUDY, SourceType.PUBLIC_DATABASE}


def prepare(session, client, *, allow_empty=False):
    """The researched topics a customer link opens with, in topic order.

    Only explicitly public, web-sourced statements qualify; a customer GET
    never runs research and confidential rows are never exposed. The newest
    usable statement per topic wins.
    """
    public = {}
    for row in session.scalars(select(ClientFact).where(ClientFact.client_id == client.id,
                                                        ClientFact.key.in_(TOPIC_KEYS))
                              .order_by(ClientFact.updated_at, ClientFact.id)):
        if (row.confidentiality == Confidentiality.PUBLIC and row.source_type in PUBLIC_SOURCES
                and web_source(row.source_url)
                and row.fact_status not in {FactStatus.ARCHIVED, FactStatus.REJECTED, FactStatus.CONTRADICTORY, FactStatus.OUTDATED}
                and not row.is_disputed):
            public[row.key] = dict(key=row.key, label=twin.CATALOG_BY_KEY[row.key]['label'],
                value=row.value, source_url=row.source_url, source_title=row.source_title,
                researched_at=row.updated_at.isoformat(), fact_id=row.id)
    if not public and not allow_empty:
        raise ValueError('Noch keine belegten öffentlichen Angaben vorhanden. Bitte Website und Recherche-Zugang prüfen und die Vorbereitung erneut starten. Es wurde kein Kundenlink erstellt.')
    missing = [twin.CATALOG_BY_KEY[key]['label'] for key in TOPIC_KEYS if key not in public]
    return [public[key] for key in TOPIC_KEYS if key in public], missing
