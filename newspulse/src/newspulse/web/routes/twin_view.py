"""One profile page for statements, company knowledge and its market context."""
import base64
from html import escape

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.orm import Session
from ..app import get_db
from ..mandates import mandate_or_404

router = APIRouter()

#: The tabs the mandate's file is split into, and what each one loads.
VIEWS = ('profile', 'rivals', 'guide')


def render_profile(request, session, client, *, view='profile', **extra):
    # Lazy imports keep the existing form handlers free to render this page too.
    from .profile import profile_context
    from .rivals_view import rivals_context
    from .client import market_context

    from ..react_pages import render
    data = dict(client=client, view=view)
    if view in ('profile', 'guide'):
        data['company'] = profile_context(request, session, client, **extra)
    if view == 'rivals':
        data.update(rivals=rivals_context(session, client), market=market_context(session, client))
    return render(request, 'profile', data)


@router.get('/client/{client_id}/twin', response_class=HTMLResponse)
def twin_page(client_id: int, request: Request, session: Session = Depends(get_db)):
    return render_profile(request, session, mandate_or_404(session, client_id))


@router.get('/client/{client_id}/kickoff')
def retired_kickoff(client_id: int, session: Session = Depends(get_db)):
    # The 20-question kick-off is gone; the 22 customer questions on the
    # profile replace it. Old bookmarks land there instead of on a 404.
    mandate_or_404(session, client_id)
    return RedirectResponse(f'/client/{client_id}/twin', status_code=303)


@router.get('/client/{client_id}/logo')
def client_logo(client_id: int, session: Session = Depends(get_db)) -> Response:
    """The mandate's logo as an image every page can point at.

    Its stored mark when there is one, otherwise the monogram on the mandate's
    colour, so an ``<img>`` never needs a fallback of its own."""
    from ... import branding
    from ..app import logo_src
    client = mandate_or_404(session, client_id)
    headers = {'Cache-Control': 'private, max-age=600'}
    src = logo_src(client.logo_url)
    if src.startswith('data:'):
        kind, data = src[5:].split(';base64,', 1)
        return Response(base64.b64decode(data), media_type=kind, headers=headers)
    if src:
        return RedirectResponse(src, status_code=302, headers=headers)
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
           f'<rect width="64" height="64" rx="14" fill="{escape(branding.colour(client.name))}"/>'
           '<text x="32" y="33" text-anchor="middle" dominant-baseline="middle" fill="#fff" '
           'font-family="system-ui,sans-serif" font-size="24" font-weight="700">'
           f'{escape(branding.monogram(client.name))}</text></svg>')
    return Response(svg, media_type='image/svg+xml', headers=headers)
