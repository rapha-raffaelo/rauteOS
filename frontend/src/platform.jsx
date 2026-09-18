import { NewClientPage } from "./platform/NewClientPage.jsx";
import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import { ArchivePage } from "./platform/ArchivePage.jsx";
import { SettingsPage } from "./platform/SettingsPage.jsx";
import { ProfilePage } from "./platform/ProfilePage.jsx";
import "./twin.css";
import "./platform/platform.css";
const root = document.getElementById("react-platform");
function Platform() {
  const [data, setData] = useState(
    JSON.parse(document.getElementById("react-page-data").textContent),
  );
  const Page = {
    new_client: NewClientPage,
    archive: ArchivePage,
    settings: SettingsPage,
    profile: ProfilePage,
  }[root.dataset.page];
  return <Page data={data} onData={setData} />;
}
if (root) createRoot(root).render(<Platform />);
