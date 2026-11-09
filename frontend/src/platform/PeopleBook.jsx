import React, { useState } from "react";
import { Action, Field, Notice, t } from "./shared.jsx";

// The mandate's phone book (newspulse.people). Plain forms that post and come
// back; a media contact is who RAUTE proposes as a chance's speaker.

function Head() {
  return (
    <svg className="pb-photo pb-photo--none" viewBox="0 0 48 48" aria-hidden="true">
      <circle cx="24" cy="18" r="8" />
      <path d="M9 42c1.5-8 7.6-12 15-12s13.5 4 15 12z" />
    </svg>
  );
}

function PersonForm({ action, person = {}, onCancel }) {
  return (
    <form method="post" action={action} className="pb-form">
      <div className="pb-form__grid">
        <Field name="name" label="Name" value={person.name} required maxLength={200} autoFocus={!person.name} />
        <Field name="position" label="Position" value={person.position} maxLength={200} />
        <Field name="phone" label="Telefon" type="tel" value={person.phone} maxLength={80} />
        <Field name="email" label="E-Mail" type="email" value={person.email} maxLength={320} />
        <Field name="linkedin_url" label="LinkedIn-Profil" value={person.linkedin_url} maxLength={500} placeholder="https://www.linkedin.com/in/…" />
        <Field name="topics" label="Themenverantwortung" type="textarea" rows={2} value={person.topics} maxLength={2000}
          placeholder={t("z. B. Finanzierung, Regulierung, Produkt")} />
      </div>
      <label className="pb-inline pb-media-check">
        <input type="checkbox" name="media_contact" value="1" defaultChecked={!!person.media_contact} />
        {t("Medienansprechpartner: darf zitiert werden und wird für Pitches vorgeschlagen")}
      </label>
      <div className="wl-form__acts">
        <button type="submit" className="btn btn--go">{t("Speichern")}</button>
        <button type="button" className="btn btn--quiet" onClick={onCancel}>{t("Abbrechen")}</button>
      </div>
    </form>
  );
}

function Card({ person, base, onEdit }) {
  return (
    <article className="pb-card" id={`kontakt-${person.id}`}>
      <div className="pb-card__top">
        <Head />
        <div className="pb-card__who">
          <h3>{person.name}</h3>
          {person.position && <p>{person.position}</p>}
        </div>
        {person.linkedin_url && (
          <a className="pb-li" href={person.linkedin_url} target="_blank" rel="noopener noreferrer"
            aria-label={`${person.name} ${t("auf LinkedIn")}`} title={t("LinkedIn-Profil öffnen")}>
            <svg className="ico" aria-hidden="true"><use href="#ico-linkedin" /></svg>
          </a>
        )}
      </div>
      <p className="pb-reach">
        {person.phone && <a href={`tel:${person.phone.replace(/[^\d+]/g, "")}`}>{person.phone}</a>}
        {person.email && <a href={`mailto:${person.email}`}>{person.email}</a>}
        {!person.phone && !person.email && <span className="pb-muted">{t("Noch keine Telefonnummer oder E-Mail.")}</span>}
      </p>
      {person.topics && <p className="pb-topics" title={person.topics}><span>{t("Themen")}:</span> {person.topics}</p>}
      <div className="pb-card__acts">
        <Action action={`${base}/kontakte/${person.id}/medien`} values={{ media_contact: person.media_contact ? "" : "1" }}
          className={`pb-media${person.media_contact ? " pb-media--on" : ""}`}
          label={person.media_contact ? "Medien ✓" : "Medien"} />
        <button type="button" className="btn btn--quiet" onClick={onEdit}>{t("Bearbeiten")}</button>
      </div>
    </article>
  );
}

export function PeopleBook({ people = [], error = "", draft = {}, base }) {
  const [editing, setEditing] = useState(draft.id ?? null);
  const media = people.filter((p) => p.media_contact).length;
  return (
    <section id="kontakte" className="platform-panel pb">
      <header className="pb-head">
        <div>
          <h2>{t("Kontakte & Sprecher")}</h2>
          <p>{people.length
            ? `${people.length} ${t(people.length === 1 ? "Kontakt" : "Kontakte")} · ${media} ${t("Medienansprechpartner")}`
            : t("Wer beim Kunden spricht und erreichbar ist. Medienansprechpartner schlägt RAUTE für Pitches vor.")}</p>
        </div>
        {editing !== "neu" && <button type="button" className="btn btn--ghost" onClick={() => setEditing("neu")}>+ {t("Kontakt anlegen")}</button>}
      </header>
      <Notice>{error}</Notice>
      {editing === "neu" && <div className="pb-card pb-card--form">
        <PersonForm action={`${base}/kontakte`} person={draft.id === "neu" ? draft : {}} onCancel={() => setEditing(null)} />
      </div>}
      {people.length > 0 && <div className="pb-grid">
        {people.map((p) => editing === p.id
          ? <div key={p.id} className="pb-card pb-card--form" id={`kontakt-${p.id}`}>
              <PersonForm action={`${base}/kontakte/${p.id}`} person={draft.id === p.id ? { ...p, ...draft } : p}
                onCancel={() => setEditing(null)} />
              <Action action={`${base}/kontakte/${p.id}/delete`} label="Kontakt löschen" className="wl-del" />
            </div>
          : <Card key={p.id} person={p} base={base} onEdit={() => setEditing(p.id)} />)}
      </div>}
    </section>
  );
}
