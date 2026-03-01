import { createRoot } from "react-dom/client";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { runStateInvariants } from "./lib/stateInvariants";
import App from "./App.tsx";
import "./index.css";

runStateInvariants();

createRoot(document.getElementById("root")!).render(
  <ErrorBoundary>
    <App />
  </ErrorBoundary>
);
