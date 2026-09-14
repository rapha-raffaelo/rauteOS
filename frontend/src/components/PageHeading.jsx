import React from 'react';

export function PageHeading({eyebrow,title,description,children}){
 return <header className="page-heading"><div>{eyebrow&&<p className="page-eyebrow">{eyebrow}</p>}<h1>{title}</h1>{description&&<p className="page-description">{description}</p>}</div>{children&&<div className="page-heading-actions">{children}</div>}</header>;
}

export function EmptyState({title,children}){
 return <section className="empty-state"><span className="empty-state-mark" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M4 5h16v14H4zM4 10h16M9 10v9"/></svg></span><h2>{title}</h2><p>{children}</p></section>;
}
