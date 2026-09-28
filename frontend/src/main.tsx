import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { MemoryProvider } from "./context/MemoryContext";
import "./index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <MemoryProvider>
        <App />
      </MemoryProvider>
    </BrowserRouter>
  </StrictMode>,
);
