import React from "react";
import { createRoot } from "react-dom/client";
import "./src/index.css";
import App from "./components/App";

const container = document.getElementById("root");
if (container) {
  const root = createRoot(container);
  root.render(<App />);
}

// PWA: registrar service worker (no bloquea el arranque)
try {
  if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("/sw.js").catch(() => {});
    });
  }
} catch {}
