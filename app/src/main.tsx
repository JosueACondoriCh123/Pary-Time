import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { CoreProvider } from "./core";
import "./fonts";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <CoreProvider>
      <App />
    </CoreProvider>
  </StrictMode>,
);
