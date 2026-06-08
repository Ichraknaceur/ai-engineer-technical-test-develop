import { useEffect, useState } from "react";
import * as api from "./api/client.js";
import HomePage from "./pages/HomePage.jsx";

// Root component: header with live health indicator + the main page.
export default function App() {
  const [health, setHealth] = useState(null);

  useEffect(() => {
    api
      .getHealth()
      .then(setHealth)
      .catch(() => setHealth({ status: "error" }));
  }, []);

  const ok = health?.status === "ok";

  return (
    <div className="app">
      <header className="app-header">
        <div>
          <h1>Quarry Extraction Pipeline</h1>
          <div className="subtitle">
            Discover and enrich quarry records from public web sources
          </div>
        </div>
        {health && (
          <div style={{ fontSize: 13, color: "var(--muted)" }}>
            <span className={`health-dot ${ok ? "ok" : "error"}`} />
            API {ok ? "healthy" : "degraded"}
          </div>
        )}
      </header>
      <HomePage />
    </div>
  );
}
