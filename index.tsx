import React from "react";
import { createRoot } from "react-dom/client";
import VocalisLabModule from "./components/VocalisLabModule";

const container = document.getElementById("root");
if (container) {
  const root = createRoot(container);
  root.render(<VocalisLabModule />);
}
