"""JSON view models for React pages; Jinja only hosts the document and bundle.

ORM rows are deliberately allowlisted. Never serialize arbitrary model columns,
relationships, credentials or request/session objects into the browser.
"""
from dataclasses import fields, is_dataclass
from datetime import date, datetime
from enum import Enum

from fastapi.responses import JSONResponse

_MODEL_FIELDS = {
    'GuideSource': 'id filename characters uploaded_at',
    'BrainOverride': 'key text version edited_at edited_by',
    'Client': 'id name active is_competitor industry country aliases keywords alert_topics excluded_terms required_terms actions_per_quarter muted_categories website',
    'ClientFact': 'key value filled_by source_url source_title is_disputed superseded_value superseded_source_url superseded_source_title superseded_filled_by',
    'ProfileProposal': 'id key value source_url source_title',
    'OnboardingAnswer': 'key value skipped answered_at',
    'Article': 'id title url source published_at',
}
_PROPERTIES = {
    'newspulse.profile.Proposal': 'from_person',
    'newspulse.profile.Checked': 'never as_age',
    'newspulse.onboarding.Question': 'is_list is_prose verb',
    'newspulse.onboarding.Completeness': 'settled remaining percent started',
    'newspulse.onboarding.SectionProgress': 'settled state',
    'newspulse.onboarding.GuideDraft': 'has_gaps',
    'newspulse.gmail_link.Link': 'is_connected may_send scope_words',
    'newspulse.themes.ThemeProbe': 'usable',
    'newspulse.industry.Candidate': 'usable',
    'newspulse.web.routes.settings.RunView': 'is_running',
    'newspulse.web.routes.client.Remaining': 'weeks in_weeks',
    'newspulse.web.routes.client.SignalRow': 'from_search deadline_soon next_in next_is_deadline next_at',
}


def view_data(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): view_data(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [view_data(v) for v in value]
    name = type(value).__name__
    if name in _MODEL_FIELDS:
        result = {key: view_data(getattr(value, key, None)) for key in _MODEL_FIELDS[name].split()}
        if name == 'OnboardingAnswer':
            from ..onboarding import entries
            result['entries'] = entries(value.value)
        if name == 'Client':
            for relation in ('competitors', 'benchmark_for'):
                result[relation] = [{'id': c.id, 'name': c.name} for c in getattr(value, relation)]
        return result
    if name in {'RivalSuggestion', 'CoachFinding', 'ThemeSuggestion'}:
        return value.model_dump(mode='json')
    if is_dataclass(value):
        result = {f.name: view_data(getattr(value, f.name)) for f in fields(value)}
        for key in _PROPERTIES.get(f'{type(value).__module__}.{name}', '').split():
            result[key] = view_data(getattr(value, key))
        return result
    raise TypeError(f'No React view contract for {name}')


def shell_data(request):
    from .. import branding, i18n, config
    from .app import assistant_context, request_language, google_auth
    from .navigation import nav_clients, nav_crumbs
    language = request_language(request)
    roster = view_data(nav_clients(request))
    for client in roster:
        client['colour'] = branding.colour(client['name'])
    return dict(clients=roster, crumbs=view_data(nav_crumbs(request)),
                path=request.url.path, query=request.url.query, language=language, timezone=str(config.local_zone()),
                translations=i18n._EN if language == 'en' else {},
                assistant=assistant_context(request),
                login=google_auth.is_configured(), user=request.scope.get('user_email'))


def tabs_data(request, client, active):
    from .routes.crisis_view import crisis_tab
    return dict(client={'id': client.id, 'name': client.name, 'is_competitor': client.is_competitor},
                active=active, crisis=view_data(crisis_tab(request, client)) if not client.is_competitor else None)


def render(request, page, context):
    from .app import templates
    from .frontend import page_assets
    from . import runlock
    data = view_data({k: v for k, v in context.items() if k not in {'request', 'last_run', 'header_date', 'frontend'}})
    if page == 'settings':
        data['run_active'] = runlock.is_running()
    if 'application/json' in request.headers.get('accept', ''):
        return JSONResponse(data, headers={'Cache-Control': 'no-store', 'Vary': 'Accept'})
    assets = page_assets('platform')
    if not assets:
        raise RuntimeError('Build the React frontend before serving RauteOS')
    return templates.TemplateResponse(request, 'react_page.html', {
        'frontend': assets, 'page': page, 'data': data,
        'page_title': {'archive': 'Archiv', 'settings': 'Einstellungen', 'profile': 'Profil', 'new_client': 'Neuer Mandant'}[page],
        'client': context.get('client'),
        'active': 'twin' if page == 'profile' else 'overview',
    }, headers={'Cache-Control': 'no-store', 'Vary': 'Accept'})
