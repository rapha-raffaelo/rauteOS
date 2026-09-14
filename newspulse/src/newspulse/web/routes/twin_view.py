"""One profile page for statements, company knowledge and its market context."""
import datetime as dt
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from markupsafe import Markup
from sqlalchemy.orm import Session
from .. import frontend
from ..app import get_db, templates, translator
from ..mandates import mandate_or_404
from .today import _fetch_last_run, _local_tz

router = APIRouter()


def render_profile(request, session, client, **extra):
    # Lazy imports keep the existing form handlers free to render this page too.
    from .profile import profile_context
    from .rivals_view import rivals_context
    from .client import market_context

    def section(name, context):
        # Only our autoescaped templates become markup, never caller-supplied HTML.
        template = templates.env.get_template(f'partials/{name}_body.html')
        return Markup(template.render(**(context | {'request': request, 't': translator(request)})))

    return templates.TemplateResponse(request, 'client_twin.html', dict(
        client=client, frontend=frontend.page_assets('twin'),
        company_section=section('client_profile', profile_context(request, session, client, **extra)),
        rivals_section=section('client_rivals', rivals_context(session, client)),
        market_section=section('client_market', market_context(session, client)),
        last_run=_fetch_last_run(session), header_date=dt.datetime.now(_local_tz()).date()))


@router.get('/client/{client_id}/twin', response_class=HTMLResponse)
def twin_page(client_id: int, request: Request, session: Session = Depends(get_db)):
    return render_profile(request, session, mandate_or_404(session, client_id))
