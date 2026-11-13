"""Request-local mailbox owner, propagated into synchronous request workers."""
from contextvars import ContextVar
import hashlib

owner: ContextVar[str] = ContextVar('gmail_owner', default='')


def key_for(email: str) -> str:
    from .worklists import member_for
    address = email.strip().casefold()
    return member_for(address) or hashlib.sha256(address.encode()).hexdigest()
