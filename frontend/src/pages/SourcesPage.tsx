import { useEffect, useMemo, useState } from "react";
import { apiRuns, apiSources, RunSummary, SourceRecord } from "../api";

export default function SourcesPage() {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [runId, setRunId] = useState<string>("");
  const [sources, setSources] = useState<SourceRecord[]>([]);
  const [error, setError] = useState<string | null>(null);

  const selected = useMemo(() => runs.find((r) => r.run_id === runId) ?? null, [runs, runId]);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const r = await apiRuns();
        if (cancelled) return;
        setRuns(r);
        if (r.length > 0) setRunId(r[0].run_id);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!runId) return;
    let cancelled = false;
    async function load() {
      try {
        const s = await apiSources(runId);
        if (!cancelled) setSources(s.sources);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [runId]);

  return (
    <div className="card">
      <h2>Kilder</h2>
      {error && <p className="muted">{error}</p>}
      <div className="row" style={{ alignItems: "center" }}>
        <div style={{ flex: 1 }}>
          <label className="muted">Vælg run</label>
          <select value={runId} onChange={(e) => setRunId(e.target.value)}>
            {runs.map((r) => (
              <option key={r.run_id} value={r.run_id}>
                {r.created_at_utc} — {r.procedure} ({r.status})
              </option>
            ))}
          </select>
        </div>
      </div>
      {selected && (
        <p className="muted" style={{ marginTop: 10 }}>
          run_id: <code>{selected.run_id}</code>
        </p>
      )}

      <div style={{ marginTop: 12 }}>
        {sources.length === 0 ? (
          <p className="muted">Ingen kilder.</p>
        ) : (
          <div style={{ overflow: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr>
                  <th align="left">source_id</th>
                  <th align="left">kind</th>
                  <th align="left">title/url/pmid</th>
                  <th align="left">hashes</th>
                  <th align="left">filer</th>
                </tr>
              </thead>
              <tbody>
                {sources.map((s) => (
                  <tr key={s.source_id} style={{ borderTop: "1px solid #23314f" }}>
                    <td style={{ padding: "10px 0" }}>
                      <code>{s.source_id}</code>
                    </td>
                    <td className="muted" style={{ padding: "10px 0" }}>
                      {s.kind}
                    </td>
                    <td className="muted" style={{ padding: "10px 0" }}>
                      {s.title ?? s.url ?? s.pmid ?? "-"}
                    </td>
                    <td className="muted" style={{ padding: "10px 0", fontSize: 12 }}>
                      <code>{s.raw_sha256.slice(0, 12)}…</code> / <code>{s.normalized_sha256.slice(0, 12)}…</code>
                    </td>
                    <td className="muted" style={{ padding: "10px 0" }}>
                      <a
                        className="muted"
                        href={`/api/runs/${encodeURIComponent(runId)}/sources/${encodeURIComponent(s.source_id)}/normalized`}
                        target="_blank"
                        rel="noreferrer"
                      >
                        norm
                      </a>
                      {" · "}
                      <a
                        className="muted"
                        href={`/api/runs/${encodeURIComponent(runId)}/sources/${encodeURIComponent(s.source_id)}/raw`}
                        target="_blank"
                        rel="noreferrer"
                      >
                        raw
                      </a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
