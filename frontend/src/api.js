export async function fetchDesk(signal) {
  const response = await fetch('/api/v1/desk', {
    credentials: 'same-origin', headers: { Accept: 'application/json' }, signal,
  });
  if (response.status === 401) throw new Error('auth');
  if (!response.ok || !response.headers.get('content-type')?.includes('application/json')) {
    throw new Error('load');
  }
  return response.json();
}

export async function writeBriefing() {
  const response = await fetch('/api/v1/desk/briefing', {
    method: 'POST', credentials: 'same-origin', headers: { Accept: 'application/json' },
  });
  const body = response.headers.get('content-type')?.includes('application/json') ? await response.json() : null;
  if (!response.ok) throw new Error(body?.detail || 'Das Briefing konnte nicht formuliert werden.');
  return body;
}
