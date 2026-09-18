import React from "react";
const shell =
  typeof document === "undefined"
    ? {}
    : JSON.parse(
        document.getElementById("react-shell-data")?.textContent || "{}",
      );
export const t = (text) => shell.translations?.[text] || text;
export const date = (value) =>
  value
    ? new Intl.DateTimeFormat(shell.language === "en" ? "en-GB" : "de-DE", {
        timeZone: shell.timezone || "Europe/Berlin",
        dateStyle: "medium",
      }).format(new Date(value))
    : "—";
export const dateTime = (value) =>
  value
    ? new Intl.DateTimeFormat(shell.language === "en" ? "en-GB" : "de-DE", {
        timeZone: shell.timezone || "Europe/Berlin",
        dateStyle: "medium",
        timeStyle: "short",
      }).format(new Date(value))
    : "—";
export const safeUrl = (value) => {
  if (!value) return "";
  const raw = value.replace(/[\x00-\x20]/g, "");
  return /^[a-z][a-z0-9+.-]*:/i.test(raw) && !/^(https?|mailto):/i.test(raw)
    ? ""
    : value;
};
export function Source({ url, children }) {
  return (
    <a href={safeUrl(url)} target="_blank" rel="noopener noreferrer">
      {children || url}
    </a>
  );
}
export function Hidden({ values = {} }) {
  return Object.entries(values).flatMap(([name, value]) =>
    (Array.isArray(value) ? value : [value]).map((v, i) => (
      <input key={`${name}-${i}`} type="hidden" name={name} value={v ?? ""} />
    )),
  );
}
export function Action({
  action,
  label,
  values,
  disabled,
  children,
  className = "",
}) {
  return (
    <form
      method="post"
      action={action}
      className={`platform-action ${className}`}
    >
      <Hidden values={values} />
      {children}
      <button type="submit" disabled={disabled}>
        {t(label)}
      </button>
    </form>
  );
}
export function Field({
  name,
  label,
  value = "",
  type = "text",
  options,
  children,
  ...props
}) {
  return (
    <label className="platform-field">
      <span>{t(label)}</span>
      {options ? (
        <select name={name} defaultValue={value ?? ""} {...props}>
          {options.map((option) => {
            const [v, text] = Array.isArray(option) ? option : [option, option];
            return (
              <option key={v} value={v}>
                {t(String(text))}
              </option>
            );
          })}
        </select>
      ) : type === "textarea" ? (
        <textarea name={name} defaultValue={value ?? ""} {...props} />
      ) : (
        <input name={name} type={type} defaultValue={value ?? ""} {...props} />
      )}
      {children}
    </label>
  );
}
export function Panel({ title, children, id }) {
  return (
    <section id={id} className="platform-panel">
      <h2>{t(title)}</h2>
      {children}
    </section>
  );
}
export function Notice({ children }) {
  return children ? (
    <p className="notice" role="status">
      {t(children)}
    </p>
  ) : null;
}
