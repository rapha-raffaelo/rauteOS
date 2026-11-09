"""Short customer URLs with independent, invitation-scoped access credentials.

Passwords are 108-bit keyed random values derived from the invitation, never
from its public slug. Rotating/revoking an invitation invalidates all sessions.
The bounded, per-process throttle complements that entropy; it is not a
replacement for an edge-wide rate limiter across multiple app replicas.
"""
import base64
import datetime as dt
import hashlib
import hmac
import threading
import time
from collections import OrderedDict

from fastapi import HTTPException
from sqlalchemy import select

from .models import Client, CustomerOnboardingInvite, CustomerOnboardingJob
from . import onboarding_workflow as workflow
from .onboarding_workflow import customer_link, invite_path

_ATTEMPTS = OrderedDict()
_LOCK = threading.Lock()
TTL = 8 * 60 * 60


def short_path(client):
    return '/onboarding/' + customer_link('', client.name).rsplit('/', 1)[-1]


def password_for(invite):
    raw = hmac.new(workflow.signing_key(), f'customer-password-v1:{invite.token_hash}'.encode(), hashlib.sha256).digest()
    text = base64.urlsafe_b64encode(raw).decode()[:18]
    return '-'.join(text[i:i+6] for i in range(0, 18, 6))


def cookie_name(slug):
    return '__Secure-raute-onboarding-' + hashlib.sha256(slug.encode()).hexdigest()[:16]


def refuse():
    raise HTTPException(401, 'Zugangsdaten ungültig oder Fragebogen nicht mehr aktiv.')


def current_invite(session, slug):
    # Fail closed for ambiguous normalized names; never choose another mandate.
    clients = [c for c in session.scalars(select(Client).where(Client.active == True, Client.is_competitor == False))
               if short_path(c) == '/onboarding/' + slug]
    if len(clients) != 1:
        refuse()
    client = clients[0]
    job = session.get(CustomerOnboardingJob, client.id)
    invite = session.get(CustomerOnboardingInvite, job.invite_id) if job and job.invite_id else None
    if not invite_path(invite):
        refuse()
    return invite, client


def throttle(slug):
    now = time.monotonic()
    with _LOCK:
        started, count = _ATTEMPTS.get(slug, (now, 0))
        if now - started >= 60:
            started, count = now, 0
        _ATTEMPTS[slug] = (started, count + 1)
        _ATTEMPTS.move_to_end(slug)
        while len(_ATTEMPTS) > 10000:
            _ATTEMPTS.popitem(last=False)
        if count >= 10:
            raise HTTPException(429, 'Zu viele Versuche. Bitte in einer Minute erneut versuchen.', headers={'Retry-After': '60'})


def sign(payload):
    return hmac.new(workflow.signing_key(), ('customer-session-v1:' + payload).encode(), hashlib.sha256).hexdigest()


def login(slug, password, request, session, response):
    throttle(slug)
    invite, _ = current_invite(session, slug)
    if not hmac.compare_digest(password.encode(), password_for(invite).encode()):
        refuse()
    expiry = min(int(time.time()) + TTL, int(invite.expires_at.timestamp()))
    payload = f'{invite.id}.{expiry}.{slug}'
    response.set_cookie(cookie_name(slug), payload + '.' + sign(payload),
                        max_age=max(0, expiry - int(time.time())), path='/api/onboarding',
                        secure=True, httponly=True, samesite='strict')


def session_invite(request, session):
    slug = request.headers.get('X-Onboarding-Slug', '')
    cookie = request.cookies.get(cookie_name(slug), '')
    try:
        ident, expiry, named, signature = cookie.split('.')
        payload = f'{ident}.{expiry}.{named}'
        if named != slug or int(expiry) <= time.time() or not hmac.compare_digest(signature, sign(payload)):
            refuse()
    except (ValueError, TypeError):
        refuse()
    invite, client = current_invite(session, slug)
    if str(invite.id) != ident:
        refuse()
    return invite, client
