import { useEffect, useState } from "react";
import { getVersion } from "./api/client";

export default function App() {
  const [version, setVersion] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getVersion()
      .then((v) => setVersion(v.version))
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)));
  }, []);

  return (
    <main className="placeholder">
      <h1>avideo</h1>
      {version && <p>Connected to avideo server {version}</p>}
      {error && <p className="error">Server not reachable: {error}</p>}
      {!version && !error && <p>Connecting…</p>}
    </main>
  );
}
