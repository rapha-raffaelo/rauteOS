import { NewClientPage } from "./NewClientPage.jsx";
// Server rendering is used only by the Python UI regression suite. Production
// renders these same components in the browser; no Jinja body is reconstructed.
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { ArchivePage } from "./ArchivePage.jsx";
import { SettingsPage } from "./SettingsPage.jsx";
import { ProfilePage } from "./ProfilePage.jsx";
import { Shell, ClientTabs } from "../shell.jsx";
export function render({ page, data, shell, tabs }) {
  const Page = {
    new_client: NewClientPage,
    archive: ArchivePage,
    settings: SettingsPage,
    profile: ProfilePage,
  }[page];
  return renderToStaticMarkup(
    <>
      {shell && <Shell data={shell} portals={false} />}
      <main className="content">
        {tabs && <ClientTabs data={tabs} path={shell.path} />}
        <div id="react-platform">
          {Page && <Page data={data} onData={() => {}} />}
        </div>
      </main>
    </>,
  );
}
