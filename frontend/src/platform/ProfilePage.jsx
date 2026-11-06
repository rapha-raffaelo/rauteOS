import React, { useState, useEffect } from "react";
import { OnboardingLinks } from "../components/OnboardingLinks.jsx";
import { TwinPage } from "../components/TwinPage.jsx";
import { PageHeading } from "../components/PageHeading.jsx";
import { ClientTitle } from "../components/ClientLogo.jsx";
import {
  Action,
  Field,
  Notice,
  Panel,
  Source,
  date,
  t,
} from "./shared.jsx";
function Guide({ data: d, base }) {
  const [guide, setGuide] = useState(d.guide_text);
  return (
    <Panel title="Kommunikations-Guide" id="guide">
      <p>
        Positionierung, Kernbotschaften, Tonalität und No-Gos für alle erzeugten
        Texte.
      </p>
      <Notice>{d.saved ? "Guide gespeichert." : d.guide_error}</Notice>
      {d.proposal && (
        <section className="platform-proposal">
          <h3>Vorschlag aus den Unterlagen — noch nicht gespeichert</h3>
          <Action action={base + "/guide"} label="Übernehmen">
            <Field
              name="comms_guide"
              type="textarea"
              label="Vorschlag prüfen"
              value={d.proposal}
              maxLength={d.max_chars}
              rows={12}
            />
          </Action>
          <a href={base + "/twin#unternehmen"}>{t("Verwerfen")}</a>
        </section>
      )}
      <div className="platform-columns">
        <div>
          <h3>{t("Quellen")}</h3>
          {d.sources.length ? (
            <ul>
              {d.sources.map((s) => (
                <li key={s.id}>
                  {s.filename} · {s.characters} Zeichen · {date(s.uploaded_at)}
                  <Action
                    action={`${base}/guide/sources/${s.id}/remove`}
                    label="entfernen"
                  />
                </li>
              ))}
            </ul>
          ) : (
            <p>
              {t(
                "Noch keine Unterlagen. Der Guide lässt sich auch einfach selbst schreiben.",
              )}
            </p>
          )}
          {!!d.sources.length && (
            <Action
              action={base + "/guide/distill"}
              label="Vorschlag erzeugen"
            />
          )}
          <form
            method="post"
            action={base + "/guide/upload"}
            encType="multipart/form-data"
          >
            <Field
              name="file"
              label={`PDF, TXT oder Markdown · höchstens ${d.max_mb} MB`}
              type="file"
              accept=".pdf,.txt,.md,.markdown"
              required
            />
            <button type="submit" className="btn btn--go">{t("Hochladen")}</button>
            <p className="panel-hint">
              Gespeichert wird der extrahierte Text, nicht die Datei.
            </p>
          </form>
          <Action
            action={base + "/guide/vorschlag"}
            label="Entwurf aus Profil und Berichterstattung"
          >
            <p>
              Liest die Recherche-Themen, die Antworten aus dem Kundenfragebogen
              und die Berichterstattung.
            </p>
          </Action>
        </div>
        <form method="post" action={base + "/guide"}>
          <label className="platform-field">
            <span>
              {t("Guide")} · {guide.length}/{d.max_chars} Zeichen
            </span>
            <textarea
              name="comms_guide"
              value={guide}
              onChange={(e) => setGuide(e.target.value)}
              maxLength={d.max_chars}
              rows={16}
            />
          </label>
          <button type="submit" className="btn btn--go">{t("Speichern")}</button>
          <p>Wirkt auf Impulse, personalisierte Nachrichten und Ask RAUTE.</p>
        </form>
      </div>
      <h3>{t("Strategie-Coach")}</h3>
      <Action action={base + "/guide/coach"} label="Jetzt prüfen">
        <p>
          Prüft den Guide gegen {d.coach_days} Tage Berichterstattung. Beratend:
          ändert nichts am Guide.
        </p>
      </Action>
      <Notice>{d.coach_error}</Notice>
      {d.findings == null ? (
        <p>Noch nicht geprüft.</p>
      ) : d.findings.length ? (
        d.findings.map((f, i) => (
          <article className="feed-item" key={i}>
            <span className="tag">{t(f.kind)}</span>
            <h4>{f.headline}</h4>
            <p>{f.detail}</p>
            {f.suggestion && <p>→ {f.suggestion}</p>}
            <ul>
              {f.evidence.map((idx) => {
                const r = d.coverage[idx];
                return r ? (
                  <li key={idx}>
                    <Source url={r.url}>{r.headline}</Source> · {r.source}
                  </li>
                ) : null;
              })}
            </ul>
          </article>
        ))
      ) : (
        <p>
          {t(
            "Nichts gefunden, woran der Guide und die Berichterstattung auseinanderlaufen.",
          )}
        </p>
      )}
    </Panel>
  );
}
// The four lines only the kick-off knows. Everything else the old company
// form held (business, founding, seat, products, competitors) is now a topic of
// the brief or a glance fact above, filled by the onboarding research.
const CONTACTS = ["pressekontakt", "sprecher", "zielmedien", "krisenkontakt"];
function Company({ data, base }) {
  const shown = (p) => CONTACTS.includes(p.key);
  const d = {...data, fields: data.fields.filter(shown), proposals: data.proposals.filter(shown),
    contradictions: data.contradictions.filter(shown)};
  const filled = d.fields.filter((f) => d.facts[f.key]?.value).length;
  return (
    <>
      <Panel title="Kontakte & Sprecher" id="profilebody">
        <dl className="profile-fact-sheet">{d.fields.filter(f => d.facts[f.key]?.value).map(f =>
          <div key={f.key}><dt>{t(f.label)}</dt><dd>{d.facts[f.key].value}</dd></div>)}</dl>
        {!filled && <p>Wer zitiert werden darf, wer abends erreichbar ist und welche Titel zählen, weiß nur der Kunde.</p>}
        <details className="profile-edit" open={Boolean(d.proposals.length || d.contradictions.length)}>
        <summary>Kontakte bearbeiten <span>{filled}/{d.fields.length} ausgefüllt</span></summary>
        <Notice>{d.research_error}</Notice>
        {!!d.proposals.length && (
          <>
            <p>
              {d.proposals.length} Vorschläge stehen bereits in ihren Feldern
              und sind noch nicht gespeichert. Geänderte Werte gelten als deine
              Angabe; unveränderte Vorschläge behalten ihre Quelle.
            </p>
            <Action
              action={base + "/profil/discard"}
              label="Alle verwerfen"
              values={{
                key: d.proposals.filter((p) => p.from_person).map((p) => p.key),
                pid: d.proposals
                  .filter((p) => !p.from_person)
                  .map((p) => p.row_id),
              }}
            />
          </>
        )}
        {!!d.contradictions.length && (
          <section>
            <h3>Von Hand gefüllt — das Netz sagt etwas anderes</h3>
            <p>
              {t(
                "Regel: Eine Angabe von Hand wird nie überschrieben. Das Netz widerspricht hier nur — ändern können Sie den Wert selbst, unten im Feld.",
              )}
              {t(
                "Verwerfen heißt: Dieser Widerspruch wird beim nächsten Abgleich nicht erneut gemeldet.",
              )}
            </p>
            {d.contradictions.map((p) => (
              <article className="feed-item" key={p.id}>
                <strong>
                  {d.fields.find((f) => f.key === p.key)?.label || p.key}
                </strong>
                <p>Deine Angabe: {d.facts[p.key]?.value}</p>
                <p>Das Netz sagt: {p.value}</p>
                <Source url={p.source_url}>
                  {p.source_title || p.source_url}
                </Source>
                <Action
                  action={base + "/profil/discard"}
                  label="Verwerfen"
                  values={{ pid: p.id }}
                />
              </article>
            ))}
          </section>
        )}
        <form method="post" action={base + "/profil"}>
          <div className="platform-fields">
            {d.fields.map((f) => {
              const fact = d.facts[f.key],
                offer = d.proposals.find((p) => p.key === f.key);
              return (
                <div
                  key={`${f.key}:${offer?.value ?? fact?.value ?? ""}`}
                  className={`prof__row ${f.long ? "platform-span " : ""}${offer ? "platform-proposal prof__row--offered" : ""}`}
                >
                  {offer && fact && (
                    <p>
                      <del>{fact.value}</del>
                    </p>
                  )}
                  <Field
                    id={`f-${f.key}`}
                    name={f.key}
                    label={f.label}
                    type={f.long ? "textarea" : "text"}
                    value={offer?.value ?? fact?.value ?? ""}
                  >
                    <small>{t(f.hint)}</small>
                  </Field>
                  {offer && (
                    <p className="prof__src prof__src--offer">
                      Vorschlag, noch nicht gespeichert ·{" "}
                      {offer.source_url ? (
                        <Source url={offer.source_url}>
                          {offer.source_title || offer.source_url}
                        </Source>
                      ) : (
                        offer.source_title ||
                        (offer.from_person
                          ? "Angabe des Mandanten"
                          : "Recherche ohne Quelle")
                      )}
                    </p>
                  )}
                  {fact && (
                    <p className="prof__src">
                      {fact.filled_by === d.by_hand
                        ? t("Ihre Angabe")
                        : `Von ${fact.filled_by}`}
                      {fact.source_url && (
                        <>
                          {" "}
                          ·{" "}
                          <Source url={fact.source_url}>
                            {fact.source_title || t("Quelle")}
                          </Source>
                        </>
                      )}
                    </p>
                  )}
                  {fact?.is_disputed && (
                    <div className="prof__old">
                      Vorher: {fact.superseded_value} ·{" "}
                      {fact.superseded_filled_by}
                      {fact.superseded_source_url && (
                        <>
                          {" "}
                          ·{" "}
                          <Source url={fact.superseded_source_url}>
                            {fact.superseded_source_title || t("Quelle")}
                          </Source>
                        </>
                      )}
                      <button type="submit" form={`forget-${f.key}`}>
                        {t("Alte Angabe verwerfen")}
                      </button>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
          <button type="submit" className="btn btn--go">{t("Profil speichern")}</button>
          <p className="panel-hint">
            Was du hier änderst, gilt als deine Angabe und wird von der KI nicht
            mehr überschrieben.
          </p>
        </form>
        {d.fields
          .filter((f) => d.facts[f.key]?.is_disputed)
          .map((f) => (
            <form
              key={f.key}
              id={`forget-${f.key}`}
              method="post"
              action={`${base}/profil/${f.key}/forget`}
            />
          ))}
        </details>
      </Panel>
    </>
  );
}
function Rivals({ data: d, base }) {
  const redirect_to = base + "/wettbewerb#wettbewerb";
  return (
    <Panel title="Wettbewerbsanalyse">
      <p>Vergleich aus den letzten {d.window_days} Tagen.</p>
      {d.voice.length > 1 ? (
        <table className="data">
          <thead>
            <tr>
              <th>{t("Unternehmen")}</th>
              <th>{t("Meldungen")}</th>
              <th>{t("Warnungen")}</th>
              <th>{t("Anteil")}</th>
            </tr>
          </thead>
          <tbody>
            {d.voice.map((v) => (
              <tr key={v.client_id}>
                <td>{companyName(v.name)}</td>
                <td>{v.mentions}</td>
                <td>{v.alerts}</td>
                <td>{(v.share * 100).toFixed(1)} %</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <Notice>
          Noch keine Vergleichsgruppe. Ein Anteil ohne Vergleich sagt nichts
          aus.
        </Notice>
      )}
      {d.rivals.map((r) => (
        <article className="feed-item" key={r.client.id}>
          <h3>{companyName(r.client.name)}</h3>
          <p>
            {r.mentions} Meldungen · {r.client.industry}
          </p>
          {r.recent.length ? (
            r.recent.map((a) => (
              <p key={a.id || a.url}>
                <Source url={a.url}>{a.title}</Source> · {a.source} ·{" "}
                {date(a.published_at)}
              </p>
            ))
          ) : (
            <p>Im Zeitraum nichts gefunden.</p>
          )}
        </article>
      ))}
      <h3>{t("Pitch-Lücken")}</h3>
      {d.gaps.length ? (
        <>
          <p>
            {d.gap_total} Medien berichten über den Wettbewerb und nie über{" "}
            {d.client.name}.
          </p>
          {d.gaps.map((g, i) => (
            <p key={i}>
              {g.source} · {g.total} Meldungen
            </p>
          ))}
        </>
      ) : (
        <p>Noch keine mehrfach belegten Lücken.</p>
      )}
      <a href={base + "/map"}>{t("Ganze Coverage Map")} →</a>

    </Panel>
  );
}
// A competitor entered as its web address reads as the site's name.
const companyName = (name) => name.replace(/^https?:\/\/(www\.)?/i, "").replace(/\/$/, "");
function RivalManagement({data: d, base}) {
  const redirect_to = base + "/wettbewerb#wettbewerber";
  return <Panel title="Vergleichsgruppe">
    <p className="panel-hint">Gegen diese Unternehmen misst RauteOS Berichterstattung und Pitch-Lücken. Verknüpfte Wettbewerber zählen nur für diesen Mandanten.</p>
    <ul className="rival-chips">
      {d.client.competitors.map((r) => <li key={r.id} className="rival-chip">
        <span>{companyName(r.name)}</span>
        <form method="post" action={`${base}/competitors/${r.id}/remove`}>
          <input type="hidden" name="redirect_to" value={redirect_to} />
          <button type="submit" aria-label={`${companyName(r.name)}: Verknüpfung lösen`} title="Verknüpfung lösen">×</button>
        </form>
      </li>)}
      {!d.client.competitors.length && <li className="rival-chip rival-chip--empty">Noch keine Wettbewerber hinterlegt.</li>}
    </ul>
    <div className="rival-add">
      <Action action={base + "/competitors/accept"} label="Hinzufügen" values={{ redirect_to }}>
        <Field name="name" label="Wettbewerber hinzufügen" placeholder="Name oder Website" required />
      </Action>
      {!!d.candidates.length && (
        <Action action={base + "/competitors"} label="Hinzufügen" values={{ redirect_to }}>
          <Field id="competitor_id" name="competitor_id" label="Aus dem Bestand wählen"
            options={d.candidates.map((c) => [c.id, c.name])} />
        </Action>
      )}
    </div>
  </Panel>;
}
const kinds = {
  studie: "Studien",
  regulierung: "Regulierungskalender",
  veranstaltung: "Veranstaltungen",
};
function remaining(r) {
  return r
    ? r.days === 0
      ? "heute"
      : r.in_weeks
        ? `in ${r.weeks} Wochen`
        : `in ${r.days} Tagen`
    : "kein Datum erkannt";
}
function Market({ data: d, base }) {
  return (
    <Panel title="Marktumfeld">
      <p>Themen-Radar: letzte {d.days} Tage</p>
      <p>{d.themes.join(" · ")}</p>
      <h3 id="radar">
        {t("Meldungen")} · {d.items.length}
      </h3>
      {d.items.length ? (
        d.items.map((a, i) => (
          <article className="feed-item" key={i}>
            <h4>
              <Source url={a.url}>{a.headline}</Source>
            </h4>
            <p>
              {a.source} · {a.author} · {date(a.published_at)}
            </p>
            <p>{a.summary}</p>
          </article>
        ))
      ) : (
        <p>
          {d.themes.length
            ? "Das Themen-Radar hat in diesem Zeitraum nichts gefunden."
            : "Für diesen Mandanten ist kein Themen-Radar eingerichtet."}{" "}
          <a href={`/settings?edit=${d.client.id}`}>
            {t("Themen hinterlegen")}
          </a>
        </p>
      )}
      {d.field_gap && (
        <Notice>
          {d.field_gap === "unusable"
            ? "Nur kuratierte Quellen: der Branchenbegriff dieses Mandanten kommt in der deutschen Presse zu selten vor, um damit zu suchen. Die gezielte Suche im Feld fehlt deshalb."
            : "Nur kuratierte Quellen: für diesen Mandanten ist keine Branche hinterlegt, und ohne sie lässt sich im Feld nicht gezielt suchen."}
        </Notice>
      )}
      {Object.entries(d.signals).map(([kind, rows]) => (
        <section id={`sig-${kind}`} key={kind}>
          <header className="platform-section-head">
            <h3>
              {kinds[kind]} · {rows.length}
            </h3>
            <Action
              action={`${base}/market/${kind}/mute`}
              label="Klasse ausblenden"
            />
          </header>
          {rows.length ? (
            rows.map((r, i) => (
              <article className="feed-item" key={i}>
                <div className="feed-item__meta">
                  {kind === "studie" ? (
                    date(r.published_at)
                  ) : (
                    <div className="sig__when">
                      {remaining(r.next_in)}
                      {r.next_in &&
                        ` · ${r.next_is_deadline ? (kind === "veranstaltung" ? "Einreichfrist" : "Frist") : kind === "veranstaltung" ? "Termin" : "gilt ab"} ${date(r.next_at)}`}
                    </div>
                  )}
                </div>
                <h4>
                  <Source url={r.url}>{r.title}</Source>
                </h4>
                <span
                  className={`tag sig__origin${r.from_search ? " sig__origin--suche" : ""}`}
                >
                  {r.from_search
                    ? "Suche · vor Verwendung prüfen"
                    : "Kuratiert"}
                </span>
                <p>
                  {r.publisher || "Herausgeber unbekannt"}
                  {r.effective_at &&
                    ` · ${kind === "veranstaltung" ? "Termin" : "gilt ab"} ${date(r.effective_at)}`}
                </p>
                {r.deadline_at && (
                  <p
                    className={
                      r.deadline_soon
                        ? "platform-deadline sig__deadline--soon"
                        : ""
                    }
                  >
                    {kind === "veranstaltung" ? "Einreichfrist" : "Frist"}{" "}
                    {date(r.deadline_at)} ·{" "}
                    {!r.until_deadline
                      ? "abgelaufen"
                      : remaining(r.until_deadline)}
                    {r.deadline_soon &&
                      ` · läuft in höchstens ${d.deadline_weeks} Wochen ab`}
                  </p>
                )}
                <p>{r.summary}</p>
              </article>
            ))
          ) : (
            <p>
              {t(
                {
                  studie:
                    "Noch keine Studie aus dem Feld dieses Mandanten gefunden.",
                  regulierung:
                    "Für dieses Feld steht derzeit nichts im Regulierungskalender.",
                  veranstaltung:
                    "Keine Veranstaltung im Feld dieses Mandanten gefunden.",
                }[kind],
              )}
            </p>
          )}
          {kind === "studie" && d.hidden_studies && (
            <p>{t("Ältere Studien werden nicht angezeigt.")}</p>
          )}
        </section>
      ))}
      {!!d.muted_kinds.length && (
        <>
          <p>{t("Ausgeblendet und nicht mehr abgerufen:")}</p>
          {d.muted_kinds.map((k) => (
            <Action
              key={k}
              action={`${base}/market/${k}/unmute`}
              label={`${kinds[k] || k} wieder einblenden`}
            />
          ))}
        </>
      )}
      <h3>{t("Wen ansprechen")}</h3>
      {[
        ["Medien im Themenfeld", d.market_outlets],
        ["Medien über den Mandanten", d.own_outlets],
        [
          "Journalistinnen und Journalisten",
          [...d.market_authors, ...d.own_authors],
        ],
      ].map(([label, rows]) => (
        <section key={label}>
          <h4>{t(label)}</h4>
          {rows.length ? (
            <ul>
              {rows.map((r, i) => (
                <li key={i}>
                  {r.name} · {r.articles} · {date(r.last_seen)}
                </li>
              ))}
            </ul>
          ) : (
            <p>
              {t(
                label === "Journalistinnen und Journalisten"
                  ? "Kein Feed in diesem Zeitraum hat einen Autor mitgeliefert."
                  : label === "Medien über den Mandanten"
                    ? "Noch keine Berichterstattung über den Mandanten."
                    : "Noch keine Daten — das Radar hat nichts gefunden.",
              )}
            </p>
          )}
        </section>
      ))}
    </Panel>
  );
}
export function ProfilePage({ data: d, onData }) {
  const [dirty, setDirty] = useState(false);
  const [ready, setReady] = useState(false);
  const [refreshError, setRefreshError] = useState("");
  useEffect(() => {
    if (!d.company?.researching || ready || !onData) return;
    const controller = new AbortController();
    const timer = setInterval(async () => {
      try {
        const response = await fetch(`/client/${d.client.id}/twin`, {
          headers: { Accept: "application/json" },
          signal: controller.signal,
        });
        if (!response.ok)
          throw new Error("Recherche-Status konnte nicht aktualisiert werden.");
        const next = await response.json();
        setRefreshError("");
        if (!next.company?.researching) {
          if (dirty) setReady(true);
          else onData(next);
        }
      } catch (error) {
        if (error.name !== "AbortError") setRefreshError(error.message);
      }
    }, 4000);
    return () => {
      clearInterval(timer);
      controller.abort();
    };
  }, [d.company?.researching, d.client.id, dirty, ready, onData]);
  useEffect(() => {
    function reveal() {
      const target = document.getElementById(decodeURIComponent(window.location.hash.slice(1)));
      if (!target) return;
      for (let node = target; node; node = node.parentElement) if (node.tagName === 'DETAILS') node.open = true;
      if (['unternehmen', 'profilebody'].includes(target.id)) target.querySelector('details')?.setAttribute('open', '');
      target.scrollIntoView?.({block:'start'});
    }
    reveal(); window.addEventListener('hashchange', reveal);
    return () => window.removeEventListener('hashchange', reveal);
  }, [d.client.id]);
  const base = `/client/${d.client.id}`;
  const view = d.view || "profile";
  // The mandate's file, split in three tabs: who the company is, whom it is
  // measured against and in what market, and how it speaks.
  const heading = {
    profile: ["Profil", "Wissen, Unternehmensangaben und Kontakte an einem Ort."],
    rivals: ["Wettbewerb", "Vergleichsgruppe, Berichterstattung und Marktumfeld."],
    guide: ["Kommunikations-Guide", "Positionierung, Tonalität, No-Gos und Unterlagen für alle erzeugten Texte."],
  }[view];
  return (
    <div className="profile-page">
      <PageHeading
        eyebrow={t(heading[0])}
        title={<ClientTitle client={d.client} />}
        description={d.client.legal_name ? `${t("Unternehmen dahinter")}: ${d.client.legal_name} · ${t(heading[1])}` : t(heading[1])}
      />
      {view === "profile" && <>
        {/* Onboarding and the contacts side by side: who to ask, next to the
            link that asks them. */}
        <div className="profile-top">
          <OnboardingLinks key={d.client.id} clientId={d.client.id} />
          <section id="unternehmen" className="profile-section" onChangeCapture={() => setDirty(true)}>
            <Notice>{refreshError}</Notice>
            {ready && (
              <Notice>
                Recherche abgeschlossen. Bitte ungespeicherte Eingaben sichern und
                die Seite neu laden, um die Vorschläge zu sehen.
              </Notice>
            )}
            <Company data={d.company} base={base} />
          </section>
        </div>
        <section id="wissen" className="profile-knowledge" aria-label={t("Wissen & Aussagen")}>
          <TwinPage clientId={d.client.id} embedded />
        </section>
      </>}
      {view === "rivals" && <>
        <section id="wettbewerber" className="profile-section"><RivalManagement data={d.rivals} base={base}/></section>
        <section id="wettbewerb" className="profile-section"><Rivals data={d.rivals} base={base} /></section>
        <section id="marktumfeld" className="profile-section"><Market data={d.market} base={base} /></section>
      </>}
      {view === "guide" && <section id="guide" className="profile-section"><Guide data={d.company} base={base} /></section>}
    </div>
  );
}
