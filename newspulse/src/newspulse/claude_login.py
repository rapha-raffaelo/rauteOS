"""Guided server login through the installed CLI; never expose terminal output or tokens."""
import datetime as dt
import json
import os
import pty
import re
import secrets
import select
import signal
import subprocess
import threading
import time
from urllib.parse import urlsplit

LOCK = threading.RLock()
TTL = 600
_current = None
_cache = (0, {})
ANSI = re.compile(r'\x1b\[[0-?]*[ -/]*[@-~]')


def login_url(output):
    for raw in re.findall(r'https://[^\s\x00-\x1f\x7f]+', ANSI.sub('', output)):
        url = raw.rstrip(').,')
        try:
            parsed = urlsplit(url)
            port = parsed.port
        except ValueError:
            continue
        if ((parsed.hostname, parsed.path) in {
                ('claude.ai', '/oauth/authorize'),
                ('console.anthropic.com', '/oauth/authorize'),
                ('platform.claude.com', '/oauth/authorize'),
                ('claude.com', '/cai/oauth/authorize'),
            } and not parsed.username and port in (None,443)):
            return url
    return None


def status(force=False):
    global _cache
    with LOCK:
        if not force and time.monotonic()-_cache[0] < 30:
            return dict(_cache[1])
        from .analyzer import claude_env
        try:
            result = subprocess.run(['claude','auth','status','--json'], env=claude_env(), capture_output=True, text=True, timeout=8)
            value = json.loads(result.stdout)
            logged_in = value.get('loggedIn')
            if not isinstance(logged_in,bool): raise ValueError()
            expiry = value.get('loginExpiresAt')
            if isinstance(expiry,str):
                try:
                    expires = dt.datetime.fromisoformat(expiry.replace('Z','+00:00'))
                    if expires.tzinfo and expires <= dt.datetime.now(dt.UTC): logged_in = False
                except ValueError: pass
            answer = {'state':'connected' if logged_in else 'login_required'}
        except (OSError, subprocess.SubprocessError, ValueError, TypeError, AttributeError):
            answer = {'state':'unknown'}
        _cache = (time.monotonic(), answer)
        return dict(answer)


def public(session):
    return {key:session.get(key) for key in ('id','state','url','message')}


def owned(id, owner):
    if not _current or _current['id'] != id or _current['owner'] != owner:
        raise KeyError('Anmeldung nicht gefunden oder abgelaufen')
    return _current


def terminate(session):
    proc=session.get('process')
    if proc and proc.poll() is None:
        try: os.killpg(proc.pid,signal.SIGTERM)
        except ProcessLookupError: pass


def start(owner):
    global _current
    with LOCK:
        if _current and _current['state'] in {'starting','waiting','checking'}:
            if _current['owner'] != owner: raise ValueError('Eine andere Person meldet Claude gerade an')
            return public(_current)
        session={'id':secrets.token_urlsafe(24),'owner':owner,'state':'starting','url':None,'message':'Anmeldung wird gestartet'}
        _current=session
        threading.Thread(target=_login,args=(session,),daemon=True).start()
        return public(session)


def _login(session):
    fd = slave = None
    try:
        from .analyzer import claude_env
        fd,slave=pty.openpty()
        # Prevent long OAuth URLs from being wrapped by the terminal.
        import fcntl,struct,termios
        fcntl.ioctl(slave,termios.TIOCSWINSZ,struct.pack('HHHH',24,4096,0,0))
        with LOCK:
            if session['state']=='cancelled': return
            proc=subprocess.Popen(['claude','auth','login','--claudeai'],stdin=slave,stdout=slave,stderr=slave,
                                  env={**claude_env(),'BROWSER':'/bin/true'},start_new_session=True,close_fds=True)
            session.update(process=proc,fd=fd)
        os.close(slave);slave=None
        deadline=time.monotonic()+TTL
        output=''
        while proc.poll() is None and time.monotonic()<deadline:
            if select.select([fd],[],[],0.25)[0]:
                try: chunk=os.read(fd,4096)
                except OSError: break
                if not chunk: break
                output=(output+chunk.decode('utf-8','replace'))[-65536:]
                url=login_url(output)
                with LOCK:
                    if url and session['state'] in {'starting','waiting'}:
                        session.update(url=url,state='waiting',message='Im Browser anmelden und gegebenenfalls den Bestätigungscode eingeben')
        if proc.poll() is None:
            try: proc.wait(timeout=2)
            except subprocess.TimeoutExpired: terminate(session)
        with LOCK:
            if session['state']=='cancelled': return
            if proc.poll()==0:
                session.update(state='checking',url=None,message='Anmeldung wird geprüft')
            else:
                session.update(state='failed',url=None,message='Anmeldung nicht abgeschlossen oder Zeitlimit erreicht. Bitte erneut starten.')
                return
        checked=status(force=True)
        with LOCK:
            session.update(state='connected' if checked['state']=='connected' else 'failed',
                           message='Claude ist angemeldet' if checked['state']=='connected' else 'Anmeldung konnte nicht bestätigt werden. Bitte erneut starten.')
    except (OSError, ValueError, subprocess.SubprocessError):
        with LOCK:
            if session['state']!='cancelled': session.update(state='failed',url=None,message='Server-Anmeldung konnte nicht gestartet werden. Bitte erneut versuchen.')
    finally:
        terminate(session)
        proc=session.get('process')
        if proc:
            try: proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                try: os.killpg(proc.pid,signal.SIGKILL);proc.wait(timeout=2)
                except (ProcessLookupError,subprocess.TimeoutExpired): pass
        with LOCK: session.pop('fd',None)
        for descriptor in (fd,slave):
            if descriptor is not None:
                try: os.close(descriptor)
                except OSError: pass


def poll(id,owner):
    with LOCK: return public(owned(id,owner))


def submit(id,owner,code):
    # Only an OAuth code, never arbitrary terminal control sequences or commands.
    if not re.fullmatch(r'[A-Za-z0-9_.~#%+/=:-]{8,4096}',code):
        raise ValueError('Bitte den vollständigen Bestätigungscode aus dem Claude-Fenster eingeben')
    with LOCK:
        session=owned(id,owner)
        if session['state']!='waiting' or session.get('fd') is None: raise ValueError('Bitte die Anmeldung erneut starten')
        try: os.write(session['fd'],(code+'\n').encode())
        except OSError: raise ValueError('Die Anmeldung ist abgelaufen. Bitte erneut starten.') from None
        session.update(state='checking',message='Bestätigung wird verarbeitet')
        return public(session)


def cancel(id,owner):
    with LOCK:
        session=owned(id,owner)
        if session['state'] not in {'connected','failed','cancelled'}:
            session.update(state='cancelled',url=None,message='Anmeldung abgebrochen')
            terminate(session)
        return public(session)
