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
# English versions; every question and topic title exists in both languages.
TEXT_EN = {
    'Q01.01': "Which stories, decisions and turning points have shaped your company that outsiders hardly know about so far?",
    'Q01.02': "Which business goals and strategic priorities matter most over the next 12 to 24 months?",
    'Q01.03': "How do your products work, or how are your services actually delivered in practice?",
    'Q01.04': "What concrete problem do your most important products or services solve, and what measurable or tangible benefit do they create?",
    'Q01.05': "What truly sets your products or services apart from the alternatives available?",
    'Q01.06': "Which new products, services or developments of your existing offering are you planning for the next 6 to 24 months?",
    'Q01.07': "Which figures and developments best illustrate the size, success and economic significance of your company?",
    'Q01.08': "Who are your most important customer and user groups?",
    'Q01.09': "How do you win new customers, and what does a typical sales, buying or commissioning process look like?",
    'Q01.10': "Why do potential customers decide for or against your company?",
    'Q01.11': "Why do you lose customers or existing customer relationships?",
    'Q01.12': "How do you assess your company's position in the markets that matter to you?",
    'Q01.13': "Which developments in your market and competitive environment are still little known publicly but could significantly change the market in future?",
    'Q01.14': "Which external players or conditions does your business depend on significantly?",
    'Q01.15': "Which concrete customer cases demonstrate the benefit of your products or services?",
    'Q01.16': "Which developments in your company are currently going particularly well or better than expected?",
    'Q01.17': "Which business challenges or barriers to growth matter most at the moment?",
    'Q01.18': "Where do you currently see the biggest untapped opportunities?",
    'Q01.19': "Which regulatory, legal, operational or reputational matters do we need to know about to assess your company and its risks correctly?",
    'Q01.20': "What do you see fundamentally differently from other players in your industry?",
    'Q01.21': "Which experiences from your day-to-day business would help outsiders better understand your business or your market?",
    'Q01.22': "How is your company perceived by different stakeholder groups, and where would you like to change that perception?",
}
HINTS_EN = {
    'Q01.01': "What personal experiences, particular challenges, surprising developments or bold decisions lie behind the founding and growth of your company? Were there decisive moments, setbacks, coincidences or changes that mattered greatly for your success today but have so far played little part in how the company is presented publicly? What background and stories should one know to truly understand your company?",
    'Q01.02': "Where possible, please also say how you would recognise that each goal has been achieved.",
    'Q01.03': "We have already researched the publicly available information about your offering. What interests us most is what matters beyond that: How exactly are your products used or your services delivered? Which technologies, methods, work steps or special skills are involved? What do outsiders often find hard to understand, what challenges arise in practice, and which details are essential to really understand your offering?",
    'Q01.04': "How do your customers manage today without your offering? What difficulties, costs or limitations does that cause? What changes when they use your product or engage your service?",
    'Q01.05': "What advantages come, for example, from technology, quality, expertise, methodology, speed, results, cost-effectiveness or customer service? Which of these advantages can be proven or are hard for competitors to copy? And in which respects might other providers or solutions be stronger?",
    'Q01.06': "Please state the stage of development or planning for each, the expected timing, its strategic importance and, where already apparent, the customer problem you intend to address.",
    'Q01.07': "Beyond the publicly available company figures, we are particularly interested in current numbers, developments and milestones that make your company and its performance tangible. Which metrics show, for example, growth, demand, market presence, customer development or the impact of your products and services? Which developments are especially noteworthy? Where possible, please give the time period for each and indicate which information may be used publicly.",
    'Q01.08': "Where relevant, please distinguish between the people who use your products or services, subject-matter decision-makers, budget holders, procurement, management, internal champions and anyone else who can influence or block a decision to buy or commission.",
    'Q01.09': "Through which channels do new business opportunities arise? What steps does a decision go through, how long does it typically take, and what role do sales, personal relationships, partners, tenders, referrals or digital channels play?",
    'Q01.10': "What are the decisive reasons why prospects buy your products or commission your services, or ultimately decide against them? What role do price, trust, quality, scope of service, competition or internal decision processes on the customer side play, for example? Can you give concrete examples of deals won and lost?",
    'Q01.11': "For what reasons do customers end the collaboration, cancel contracts, not commission you again or switch to competitors? What role do price, quality, results, customer service, changing requirements or economic developments on the customer side play, for example? Are there recurring patterns, and what do you do to retain customers over the long term?",
    'Q01.12': "In which markets and customer segments are you particularly strong, and what role do you play there? How do you rate your market position compared with other providers? Where do you see your greatest strengths, where are your disadvantages, and in which areas do you want to strengthen your position in future? Are there features of the market structure or competitive dynamics that are hard to see from the outside?",
    'Q01.13': "Which changes are already emerging from your market knowledge that outsiders can hardly see yet? Which new technologies, products, services or business models do you think competitors or other market players are working on? Which new providers, research approaches, partnerships or shifts in customer behaviour could change the current balance of the market? Which of these developments do you consider particularly relevant, and what opportunities or risks do they create for your company?",
    'Q01.14': "Please name, for example, strategic partners, suppliers, technology platforms, sales partners, specialised service providers, subcontractors, industry associations, authorities, regulators or other players with considerable influence on your products, your service delivery or your market success.",
    'Q01.15': "What was the customer's starting situation, which product was used or which service delivered, and what results were achieved? Which customer references may be named, and for which results are there reliable data, approvals or other evidence?",
    'Q01.16': "Which products, services, customer groups, markets or initiatives are developing positively? What, if anything, surprised you about this, and how do you explain the development?",
    'Q01.17': "Please look explicitly beyond communications: Which problems are affecting demand, sales, growth, profitability, expansion, product development, service quality, delivery or competitiveness? What have you done about them so far?",
    'Q01.18': "Which customer groups, markets, products, services or new business areas could become relevant? What has so far prevented you from tapping this potential, and which strategic decisions or trade-offs are involved?",
    'Q01.19': "These may include, for example, regulatory restrictions, permits, intellectual property, ongoing disputes, product or service quality, liability issues, cyber incidents, supply chain risks, capacity bottlenecks, sensitive HR matters or critical public debates.",
    'Q01.20': "On which topics, developments or widely held beliefs do you disagree with the prevailing view? What, in your view, is often misjudged or overlooked in your industry? Which of your own experiences, observations or data led you to this view?",
    'Q01.21': "Think, for example, of unusual customer reactions, unexpected uses of your products, particular experiences in delivering your services, exceptional customer projects, wrong decisions, turning points, failed attempts or behind-the-scenes situations that normally never appear on presentation slides.",
    'Q01.22': "Your company deals with various stakeholder groups, for example customers, prospective customers, employees, applicants, business partners, investors or the public. How would you assess the current perception of your company among each of these groups? Are there clear differences, misunderstandings or ideas that, in your view, do not match reality? Do you already have concrete ideas about which stakeholder groups' perception should change, in which direction, and which of your business goals this would support?",
}
SECTION_EN = 'Company identity and strategy'
TOPIC_LABELS_EN = {
    'R01.01': "Company identity",
    'R02.01': "Legal company data",
    'R03.01': "Company size",
    'R04.01': "Management and leadership team",
    'R05.01': "Company description",
    'R06.01': "Products and services",
    'R07.01': "Target markets and customer segments",
    'R08.01': "Customers and references",
    'R09.01': "Partners and network",
    'R10.01': "Owners, investors and funding",
    'R11.01': "Technologies, patents and special expertise",
    'R12.01': "Company history and milestones",
    'R13.01': "Brand identity",
    'R14.01': "Digital presence",
    'R15.01': "Media coverage to date",
    'R16.01': "Public positioning",
    'R17.01': "Evidence and credibility",
    'R18.01': "Events and public activities",
    'R19.01': "Regulatory environment",
    'R20.01': "Public reputation and track record",
    'R21.01': "Competitors and competitive landscape",
}
# Unannounced plans and known risks stay internal; every other answer
# already needs approval before it is used outside the agency.
RESTRICTED = {'Q01.06', 'Q01.19'}


def questions():
    return [dict(key=key, text=twin.CATALOG_BY_KEY[key]['label'], help=HINTS[key], section=SECTION,
                 text_en=TEXT_EN[key], help_en=HINTS_EN[key], section_en=SECTION_EN,
                 choices=[], single_choice=False)
            for key in QUESTION_KEYS]


def with_english_label(item):
    """A prefill row as the customer page needs it; stored rows predate the English title."""
    return {**item, 'label_en': TOPIC_LABELS_EN.get(item['key'], item['label'])}


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
