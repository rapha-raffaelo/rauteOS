"""One profile page for statements, company knowledge and its market context."""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from ..app import get_db
from ..mandates import mandate_or_404

router = APIRouter()


def render_profile(request, session, client, **extra):
    # Lazy imports keep the existing form handlers free to render this page too.
    from .profile import profile_context
    from .rivals_view import rivals_context
    from .client import market_context

    from ..react_pages import render
    return render(request, 'profile', dict(
        client=client,
        company=profile_context(request, session, client, **extra),
        rivals=rivals_context(session, client),
        market=market_context(session, client)))


@router.get('/client/{client_id}/twin', response_class=HTMLResponse)
def twin_page(client_id: int, request: Request, session: Session = Depends(get_db)):
    return render_profile(request, session, mandate_or_404(session, client_id))
