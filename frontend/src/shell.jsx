import React, { useState, useEffect, useRef } from "react";
import { createRoot } from "react-dom/client";
import { createPortal } from "react-dom";
import { t, Action } from "./platform/shared.jsx";
export function ClientTabs({ data, path = window.location.pathname }) {
  const { client, active, crisis } = data;
  const base = `/client/${client.id}`;
  if (client.is_competitor)
    return (
      <p className="panel-hint">
        {t(
          "Vergleichsunternehmen. Hier steht seine Berichterstattung — Impulse, Berichte und Profil führt RauteOS nur für Mandanten.",
        )}
      </p>
    );
  const group = [
    "opportunities",
    "heute",
    "texte",
    "issues",
    "plan",
    "krise",
  ].includes(active)
    ? "opportunities"
    : [
          "twin",
          "profile",
          "rivals",
          "market",
          "kickoff",
          "guide",
          "map",
        ].includes(active)
      ? "profile"
      : active === "overview"
        ? "archive"
        : active;
  const tabs = [
    ["client_overview", "/overview", "Overview"],
    ["opportunities", "/opportunities", "Opportunities"],
    ["profile", "/twin", "Profil"],
    ["archive", "", "Archiv"],
    ["visibility", "/ki", "KI-Sichtbarkeit"],
  ];
  const views = [
    ["opportunities", "/opportunities", "Chancen"],
    ["texte", "/advice", "Impulse"],
    ["issues", "/issues", "Issues"],
    ["plan", "/plan", "Plan"],
    ...(crisis?.has_history ? [["krise", "/krise", "Krise"]] : []),
  ];
  return (
    <>
      <nav className="subtabs" aria-label={t("Mandant")}>
        {tabs.map(([key, suffix, label]) => (
          <a
            key={key}
            href={base + suffix}
            className={key === group ? "active" : undefined}
            aria-current={key === group ? "page" : undefined}
          >
            {t(label)}
            {key === "opportunities" && crisis?.open_id && (
              <span className="workspace-crisis">{t("Krise offen")}</span>
            )}
          </a>
        ))}
      </nav>
      {group === "opportunities" && active !== "heute" && (
        <nav className="workspace-links" aria-label={t("Ansicht in Opportunities")}>
          {views.map(([key, suffix, label]) => <a key={key} href={base + suffix} aria-current={key === active ? 'page' : undefined}>{t(label)}</a>)}
        </nav>
      )}
      {crisis?.offer && (
        <div className="koffer">
          <strong>{t("Krise?")}</strong>
          <span>{crisis.offer.headline}</span>
          <span>
            {crisis.offer.trigger === "kategorie"
              ? t("Als Krise eingestuft")
              : `${crisis.offer.outlets} ${t("Medien in 24 Stunden")}`}
          </span>
          {["declare", "dismiss"].map((action) => (
            <Action
              key={action}
              action={`/crisis/${action}`}
              label={action === "declare" ? "Krise erklären" : "Verwerfen"}
              values={{
                client_id: client.id,
                article_id: crisis.offer.article_id,
                redirect_to: action === "declare" ? base + "/krise" : path,
              }}
            />
          ))}
        </div>
      )}
    </>
  );
}
export function Shell({ data, portals = true }) {
  const [open, setOpen] = useState(false);
  const toggle = useRef();
  const { path, query, clients, crumbs, language, assistant } = data;
  useEffect(() => {
    const side = document.getElementById("react-sidebar");
    side?.classList.add("has-menu-toggle");
    side?.classList.toggle("is-expanded", open);
  }, [open]);
  const link = (href, label, icon) => {
    const selected =
      href === "/"
        ? path === "/"
        : path === href || path.startsWith(href + "/");
    return (
      <a
        key={href}
        href={href}
        className={`side__row${selected ? " is-on" : ""}`}
        aria-current={selected ? "page" : undefined}
      >
        {icon && (
          <svg className="ico side__icon" aria-hidden="true">
            <use href={"#ico-" + icon} />
          </svg>
        )}
        {t(label)}
      </a>
    );
  };
  const params = new URLSearchParams(assistant);
  const current = new URLSearchParams(query);
  if (path.endsWith("/opportunities") && current.get("context")) {
    params.set("scope", "opportunity");
    params.set("opportunity_kind", current.get("kind") || "developed");
    params.set("opportunity_id", current.get("context"));
  }
  const ask = "/ask?" + params;
  useEffect(() => {
    if (current.has("assistant") && path !== "/ask")
      window.location.assign(ask);
  }, []);
  const sidebar = (
    <div
      onKeyDown={(e) => {
        if (e.key === "Escape" && open) {
          setOpen(false);
          toggle.current?.focus();
        }
      }}
      style={{ display: "contents" }}
    >
      {/* Die Marke. Liegt als Datei unter /static/logo.svg; fehlt sie, steht
          die Wortmarke da — so ist der Platz schon richtig, bevor die Datei
          da ist, und das Austauschen ändert keine Zeile Code. */}
      <a className="side__brand" href="/" aria-label="raute + kopf">
        <img
          className="side__logo"
          src="/static/logo.svg"
          alt=""
          onError={(e) => {
            e.currentTarget.hidden = true;
            e.currentTarget.nextSibling?.removeAttribute("hidden");
          }}
        />
        <span className="side__word" hidden>
          raute<span className="side__plus">+</span>kopf
        </span>
      </a>
      <button
        ref={toggle}
        className="side__toggle"
        type="button"
        aria-label={t(open ? "Menü schließen" : "Menü öffnen")}
        aria-expanded={open}
        aria-controls="workspace-navigation workspace-account"
        onClick={() => setOpen(!open)}
      >
        <svg className="ico" viewBox="0 0 24 24" aria-hidden="true">
          <path d="M4 6h16M4 12h16M4 18h16" />
        </svg>
      </button>
      <nav
        id="workspace-navigation"
        className="side__nav"
        aria-label={t("Navigation")}
      >
        <div className="side__sect">{t("Übersicht")}</div>
        {link("/desk", "Desk", "desk")}
        {link("/clients", "Clients", "clients")}
        {link("/assets", "Assets", "texte")}
        <details
          className="side-tools"
          open={
            ["/today", "/", "/archive", "/contacts", "/journalists"].includes(
              path,
            ) || undefined
          }
        >
          <summary className="side__sect">{t("Weitere Werkzeuge")}</summary>
          {link("/today", "Heute")}
          {link("/", "Portfolio")}
          {link("/archive", "Archiv")}
          {link("/contacts", "Kontakte")}
        </details>
        {!!clients.length && (
          <div className="side__sect">
            {t("Mandanten")}
            <span className="side__n">{clients.length}</span>
          </div>
        )}
        {clients.map((c) => {
          const selected =
            path === `/client/${c.id}` || path.startsWith(`/client/${c.id}/`);
          return (
            <a
              key={c.id}
              href={`/client/${c.id}/overview`}
              className={`side__row side__cl${selected ? " is-on" : ""}`}
              aria-current={selected ? "page" : undefined}
            >
              <span className="side__dot" style={{ background: c.colour }} />
              <span className="side__nm">{c.name}</span>
              {c.alerts > 0 && <span className="side__badge">{c.alerts}</span>}
            </a>
          );
        })}
        <a href="/mandant/neu" className="side__row side__new">
          <span className="side__plus">+</span>
          <span className="side__newl">{t("Neuer Mandant")}</span>
        </a>
      </nav>
      <div id="workspace-account" className="side__foot">
        <details className="quiet-actions side-language">
          <summary>{t("Sprache")}</summary>
          <div className="seg" role="group" aria-label={t("Sprache")}>
            {["de", "en"].map((code) => (
              <form
                key={code}
                method="post"
                action={`/language/${code}?next=${encodeURIComponent(path + (query ? "?" + query : ""))}`}
              >
                <button
                  className={`seg__b${language === code ? " is-on" : ""}`}
                  aria-pressed={language === code}
                >
                  {code.toUpperCase()}
                </button>
              </form>
            ))}
          </div>
        </details>
        {link("/settings", "Einstellungen")}
        {data.login && (
          <form method="post" action="/logout" className="side__out">
            <button className="side__row side__outbtn" title={t("Abmelden")}>
              <span className="side__nm">{data.user || t("Abmelden")}</span>
              <span aria-hidden="true">⏻</span>
            </button>
          </form>
        )}
      </div>
    </div>
  );
  const topbar = (
    <div className="topbar">
      <nav className="crumbs" aria-label={t("Pfad")}>
        {crumbs.mandate ? (
          <>
            <a href={crumbs.area_href}>{t(crumbs.area)}</a>
            <span className="crumbs__sep" aria-hidden="true">
              /
            </span>
            <a className="crumbs__here" href={crumbs.mandate_href}>
              {crumbs.mandate}
            </a>
          </>
        ) : (
          <span className="crumbs__here">{t(crumbs.area)}</span>
        )}
      </nav>
      <div className="topbar__r">
        <form
          className="topsearch"
          method="get"
          action="/archive"
          role="search"
        >
          <svg className="ico topsearch__ico" aria-hidden="true">
            <use href="#ico-suche" />
          </svg>
          <input
            className="topsearch__in"
            type="search"
            name="q"
            autoComplete="off"
            defaultValue={path === "/archive" ? current.get("q") || "" : ""}
            placeholder={t("Archiv durchsuchen…")}
            aria-label={t("Archiv durchsuchen")}
          />
          <button type="submit" className="topsearch__go">
            {t("Suchen")}
          </button>
        </form>
        <a className="askraute" href={ask} data-raute-open>
          <svg className="ico askraute__ico" aria-hidden="true">
            <use href="#ico-raute" />
          </svg>
          Ask RAUTE
        </a>
      </div>
    </div>
  );
  if (!portals)
    return (
      <>
        <aside className="side">{sidebar}</aside>
        {topbar}
      </>
    );
  return (
    <>
      {createPortal(sidebar, document.getElementById("react-sidebar"))}
      {createPortal(topbar, document.getElementById("react-topbar"))}
    </>
  );
}
const root = document.getElementById("react-shell");
if (root)
  createRoot(root).render(
    <Shell
      data={JSON.parse(document.getElementById("react-shell-data").textContent)}
    />,
  );
const tabs = document.getElementById("react-client-tabs");
if (tabs)
  createRoot(tabs).render(
    <ClientTabs
      data={JSON.parse(document.getElementById("react-tabs-data").textContent)}
    />,
  );
