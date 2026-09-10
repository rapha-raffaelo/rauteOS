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
