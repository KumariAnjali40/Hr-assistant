import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { initAuth } from "./auth";
import "./styles.css";

initAuth()
  .then(() => createRoot(document.getElementById("root")).render(<App />))
  .catch((e) => {
    document.getElementById("root").textContent = "Could not reach the sign-in service. " + (e?.message || "");
  });
