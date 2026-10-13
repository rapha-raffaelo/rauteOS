// The test page shares the real questionnaire UI but never calls customer APIs.
export function createDemoApi(initial) {
  const key = 'raute-onboarding-demo-v1';
  let state = structuredClone(initial);
  try { const saved = JSON.parse(sessionStorage.getItem(key)); if (saved) state = {...state, ...saved}; } catch {}
  const api = async (path = '', method = 'GET', body = {}) => {
    let answer;
    if (path.startsWith('/answers/')) {
      const id = path.slice('/answers/'.length);
      if (!state.questions.some(q => q.key === id)) throw new Error('Unbekannte Frage');
      answer = {value: body.value || '', skipped: !!body.skipped};
      state.answers = {...state.answers, [id]: answer};
    } else if (path === '/prefill') {
      state.prefill_confirmed = true;
      state.prefill = state.prefill.map(p => ({...p, ...(body.corrections?.[p.key] ? {customer_value: body.corrections[p.key]} : {})}));
    } else if (path === '/complete') state.completed = true;
    if (method !== 'GET') {
      try { sessionStorage.setItem(key, JSON.stringify(state)); } catch {}
    }
    return structuredClone(answer || state);
  };
  api.reset = () => { state = structuredClone(initial); try {sessionStorage.removeItem(key);} catch {} };
  return api;
}
