// Shortens a text at the last whole word before `limit`, never inside one.
export function clip(text, limit) {
  const value = String(text || '');
  if (value.length <= limit) return value;
  const cut = value.slice(0, limit);
  const space = cut.lastIndexOf(' ');
  return `${(space > limit / 2 ? cut.slice(0, space) : cut).replace(/[\s,;:.–-]+$/, '')} …`;
}
