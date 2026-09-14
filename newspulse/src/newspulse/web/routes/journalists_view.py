"""Compatibility link into the shared contact workspace."""
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

router = APIRouter()


@router.get('/journalists')
def journalists_page(request: Request):
    query = request.url.query
    return RedirectResponse('/contacts' + ('?' + query if query else ''), status_code=303)
