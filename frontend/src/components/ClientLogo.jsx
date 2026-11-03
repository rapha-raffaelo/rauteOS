import React from 'react';

// The mandate's mark wherever its name stands. The server answers with the
// monogram when no logo is stored, so the image never needs a fallback here.
export function ClientLogo({id, size = 'sm'}) {
  return <img className={`client-logo client-logo--${size}`} src={`/client/${id}/logo`} alt="" loading="lazy" decoding="async" />;
}

export function ClientTitle({client}) {
  return <span className="profile-title"><ClientLogo id={client.id} size="lg" /><span>{client.name}</span></span>;
}
