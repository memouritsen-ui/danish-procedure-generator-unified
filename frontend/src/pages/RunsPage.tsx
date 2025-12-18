import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { apiRuns, RunSummary } from "../api";

export default function RunsPage() {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const r = await apiRuns();
        if (!cancelled) setRuns(r);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="card">
      <h2>Runs</h2>
      {error && <p className="muted">{error}</p>}
      {runs.length === 0 ? (
        <p className="muted">Ingen runs endnu.</p>
      ) : (
        <div style={{ overflow: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                <th align="left">Tid (UTC)</th>
                <th align="left">Procedure</th>
                <th align="left">Status</th>
                <th align="left">Links</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => (
                <tr key={r.run_id} style={{ borderTop: "1px solid #23314f" }}>
                  <td className="muted" style={{ padding: "10px 0" }}>
                    {r.created_at_utc}
                  </td>
                  <td style={{ padding: "10px 0" }}>{r.procedure}</td>
                  <td className="muted" style={{ padding: "10px 0" }}>
                    {r.status}
                  </td>
                  <td style={{ padding: "10px 0" }}>
                    <Link to={`/runs/${encodeURIComponent(r.run_id)}`} className="muted">
                      Åbn
                    </Link>
                    {" · "}
                    <a href={`/api/runs/${encodeURIComponent(r.run_id)}/docx`} className="muted">
                      DOCX
                    </a>
                    {" · "}
                    <a href={`/api/runs/${encodeURIComponent(r.run_id)}/bundle`} className="muted">
                      Bundle
                    </a>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
