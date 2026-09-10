export async function journalistRequest(path = '', options = {}) {
  const response = await fetch(`/api/v1/${path}`, {
    ...options, credentials: 'same-origin',
    headers: {Accept: 'application/json', ...(options.body ? {'Content-Type': 'application/json'} : {}), ...options.headers},
  });
  const data = response.headers.get('content-type')?.includes('application/json') ? await response.json() : null;
  if (!response.ok || !data) {
    const detail = data?.detail;
    throw new Error(response.status === 401 ? 'Sitzung abgelaufen. Bitte erneut anmelden.'
      : typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map(d => d.msg).join(' · ')
      : 'Anfrage fehlgeschlagen. Bitte erneut versuchen.');
  }
  return data;
}
