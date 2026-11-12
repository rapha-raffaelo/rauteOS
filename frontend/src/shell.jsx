import OverdueTasks from './components/OverdueTasks.jsx';
import ClaudeLogin from './components/ClaudeLogin.jsx';
import React, { useState, useEffect, useRef } from "react";
import { createRoot } from "react-dom/client";
import { createPortal } from "react-dom";
import { t, Action } from "./platform/shared.jsx";
import { ClientLogo } from "./components/ClientLogo.jsx";
export function ThemeSwitch() {
  // Absent when the shell is rendered on the server (render tests): Hell.
  const root = globalThis.document?.documentElement;
  const [dark, setDark] = useState(root?.getAttribute("data-theme") === "dark");
  function flip() {
    const next = dark ? "light" : "dark";
    root.setAttribute("data-theme", next);
    try {
      localStorage.setItem("raute-theme", next);
    } catch (e) {
      // Private window or blocked storage: the switch still works for this page.
    }
    setDark(!dark);
  }
  const label = t("Dunkler Modus");
  return (
    <button type="button" className="theme-switch" onClick={flip} aria-pressed={dark} aria-label={label} title={label}>
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M9 18h6M10 21h4M12 3a6 6 0 0 0-3.6 10.8c.7.6 1.1 1.3 1.1 2.2h5c0-.9.4-1.6 1.1-2.2A6 6 0 0 0 12 3z" />
      </svg>
    </button>
  );
}
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
  // Spec 09: the prototype's six tabs. Each groups pages that already exist;
  // a group with more than one page shows them as views under the tabs.
  const groups = {
    client_overview: ["client_overview", "heute"],
    wissen: ["twin", "profile"],
    strategie: ["guide", "rivals", "market", "map"],
    // Spec 12: Medien → Themen → Assets. The Agenda (formerly Redaktionsplan)
    // and the crisis pages belong to the Themen.
    themen: ["themen", "opportunities", "issues", "krise", "texte", "plan"],
    assets: ["assets"],
    medien: ["media", "overview"],
    wirkung: ["visibility", "berichte", "monitoring_social", "monitoring_kpis"],
  };
  const group =
    Object.keys(groups).find((key) => groups[key].includes(active)) || active;
  const tabs = [
    ["client_overview", "/overview", "Überblick"],
    ["wissen", "/twin", "Kundenprofil"],
    ["strategie", "/guide", "Strategie"],
    ["medien", "/medien", "Medien"],
    ["themen", "/themen", "Themen"],
    ["assets", "/assets", "Assets"],
    ["wirkung", "/ki", "Monitoring"],
  ];
  const views = {
    strategie: [
      ["guide", "/guide", "Kommunikations-Guide"],
      ["rivals", "/wettbewerb", "Wettbewerb & Markt"],
      ["map", "/map", "Medienkarte"],
    ],
    wirkung: [
      ["visibility", "/ki", "KI-Sichtbarkeit"],
      ["monitoring_kpis", "/monitoring/kpis", "KPIs"],
    ],
  }[group];
  const current = active === "market" ? "rivals" : active === "berichte" ? "overview" : active;
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
            {key === "themen" && crisis?.open_id && (
              <span className="workspace-crisis">{t("Krise offen")}</span>
            )}
          </a>
        ))}
      </nav>
      {views && (
        <nav className="workspace-links" aria-label={t("Ansicht")}>
          {views.map(([key, suffix, label]) => <a key={key} href={base + suffix} aria-current={key === current ? 'page' : undefined}>{t(label)}</a>)}
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
  const link = (href, label, icon, count) => {
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
        {count > 0 && <span className="side__badge side__count">{count}</span>}
      </a>
    );
  };
  const params = new URLSearchParams(assistant);
  const current = new URLSearchParams(query);
  if (/\/(opportunities|assets)$/.test(path) && current.get("context")) {
    params.set("scope", "opportunity");
    params.set("opportunity_kind", current.get("kind") || "developed");
    params.set("opportunity_id", current.get("context"));
  }
  const ask = "/ask?" + params;
  const search = useRef();
  useEffect(() => {
    const focus = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        search.current?.focus();
      }
    };
    window.addEventListener("keydown", focus);
    return () => window.removeEventListener("keydown", focus);
  }, []);
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
      <a className="side__brand" href="/">
        <span className="side__mark" aria-hidden="true"></span>rauteOS
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
        <div className="side__sect">{t("Arbeitsplatz")}</div>
        {link("/desk", "Desk", "desk")}
        {link("/aufgaben", "Aufgaben", "tasks", data.tasks_open)}
        {link("/clients", "Kunden", "clients")}
        {link("/gmail", "Gmail", "media")}
        <div className="side__sect">{t("Kommunikation")}</div>
        {link("/today", "Intelligence", "intel")}
        {link("/assets", "Stories & Content", "stories")}
        {link("/contacts", "Media & Relationships", "media")}
        {link("/linkedin", "LinkedIn", "linkedin")}
        <div className="side__sect">{t("Wachstum")}</div>
        {link("/sales", "Sales CRM", "sales")}
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
              <ClientLogo id={c.id} />
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
      <nav className="mobilebar" aria-label={t("Schnellnavigation")}>
        {[
          ["/desk", "Desk", "desk"],
          ["/clients", "Kunden", "clients"],
          ["/today", "Intel", "intel"],
          ["/assets", "Stories", "stories"],
          ["/aufgaben", "Aufgaben", "tasks"],
        ].map(([href, label, icon]) => {
          const on = path === href || path.startsWith(href + "/");
          return (
            <a key={href} href={href} className={on ? "is-on" : undefined} aria-current={on ? "page" : undefined}>
              <svg className="ico" aria-hidden="true"><use href={"#ico-" + icon} /></svg>
              {t(label)}
            </a>
          );
        })}
      </nav>
      <div id="workspace-account" className="side__foot">
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
              {crumbs.mandate_id && <ClientLogo id={crumbs.mandate_id} />}
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
          action="/medien"
          role="search"
        >
          <svg className="ico topsearch__ico" aria-hidden="true">
            <use href="#ico-suche" />
          </svg>
          <input
            ref={search}
            className="topsearch__in"
            type="search"
            name="q"
            autoComplete="off"
            defaultValue={["/archive", "/medien"].includes(path) ? current.get("q") || "" : ""}
            placeholder={t("Medien durchsuchen…")}
            aria-label={t("Medien durchsuchen")}
          />
          <kbd className="topsearch__kbd" aria-hidden="true">⌘K</kbd>
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
        <div className="seg topbar__lang" role="group" aria-label={t("Sprache")}>
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
        <ThemeSwitch />
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
      <ClaudeLogin />
      <OverdueTasks />
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
