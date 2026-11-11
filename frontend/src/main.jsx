import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import "./globals.css";

const rootEl = document.getElementById("root");
if (!rootEl) {
  throw new Error("Root element #root not found in index.html");
}

createRoot(rootEl).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
