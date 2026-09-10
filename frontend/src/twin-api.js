export async function twinRequest(clientId, path = '', options = {}) {
  const headers = {Accept: 'application/json', ...options.headers};
  if (options.body && !(options.body instanceof FormData)) headers['Content-Type'] = 'application/json';
  const response = await fetch(`/api/v1/clients/${clientId}/twin${path}`, {
    ...options, headers, credentials: 'same-origin',
  });
  if (response.status === 401) throw new Error('Sitzung abgelaufen. Bitte erneut anmelden.');
  const data = response.headers.get('content-type')?.includes('application/json') ? await response.json() : null;
  if (!response.ok) {
    const detail = data?.detail;
    throw new Error(typeof detail === 'string' ? detail : Array.isArray(detail)
      ? detail.map(item => `${item.loc.at(-1)}: ${item.msg}`).join(' · ')
      : 'Anfrage fehlgeschlagen. Bitte erneut versuchen.');
  }
  if (!data) throw new Error('Keine gültige Antwort. Bitte neu laden.');
  return data;
}
