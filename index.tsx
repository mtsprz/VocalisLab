import React from "react";
import { createRoot } from "react-dom/client";
import "./src/index.css";
import App from "./components/App";
import { instalarAuthFetch } from "./utils/authFetch";

// Antes de montar la app: todo pedido al servidor lleva el token de sesión.
instalarAuthFetch();

const container = document.getElementById("root");
if (container) {
  const root = createRoot(container);
  root.render(<App />);
}

// PWA: registrar service worker (no bloquea el arranque)
try {
  if ("serviceWorker" in navigator) {
    // Cuando se activa un SW nuevo (versión nueva publicada), recargar una
    // vez para mostrarla en vez de seguir con la vieja.
    const habiaControlador = !!navigator.serviceWorker.controller;
    let recargado = false;
    navigator.serviceWorker.addEventListener("controllerchange", () => {
      if (habiaControlador && !recargado) { recargado = true; window.location.reload(); }
    });
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("/sw.js", { updateViaCache: "none" })
        .then((reg) => reg.update().catch(() => {}))
        .catch(() => {});
    });
  }
} catch {}
