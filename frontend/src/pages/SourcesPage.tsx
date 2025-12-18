import { useEffect, useMemo, useState } from "react";
import { apiRuns, apiSources, apiSourceScores, RunSummary, SourceRecord, SourceScore } from "../api";
import { SourceCard } from "../components/SourceCard";

export default function SourcesPage() {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [runId, setRunId] = useState<string>("");
  const [sources, setSources] = useState<SourceRecord[]>([]);
  const [scores, setScores] = useState<SourceScore[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<"cards" | "table">("cards");

  const selected = useMemo(() => runs.find((r) => r.run_id === runId) ?? null, [runs, runId]);

  // Create a map of source_id to score for quick lookup
  const scoreMap = useMemo(() => {
    const map = new Map<string, SourceScore>();
    for (const score of scores) {
      map.set(score.source_id, score);
    }
    return map;
  }, [scores]);

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
        // Fetch both sources and scores in parallel
        const [sourcesRes, scoresRes] = await Promise.all([
          apiSources(runId),
          apiSourceScores(runId).catch(() => ({ run_id: runId, count: 0, scores: [] })),
        ]);

        if (!cancelled) {
          setSources(sourcesRes.sources);
          setScores(scoresRes.scores);
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [runId]);

  // Sort sources by score (highest first)
  const sortedSources = useMemo(() => {
    return [...sources].sort((a, b) => {
      const scoreA = scoreMap.get(a.source_id)?.composite_score ?? 0;
      const scoreB = scoreMap.get(b.source_id)?.composite_score ?? 0;
      return scoreB - scoreA;
    });
  }, [sources, scoreMap]);

  return (
    <div className="card">
      <h2>Kilder</h2>
      {error && <p className="muted">{error}</p>}

      <div className="row" style={{ alignItems: "center", gap: "1rem" }}>
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

        <div>
          <label className="muted">Visning</label>
          <select value={viewMode} onChange={(e) => setViewMode(e.target.value as "cards" | "table")}>
            <option value="cards">Kort</option>
            <option value="table">Tabel</option>
          </select>
        </div>
      </div>

      {selected && (
        <p className="muted" style={{ marginTop: 10 }}>
          run_id: <code>{selected.run_id}</code>
          {scores.length > 0 && (
            <span style={{ marginLeft: "1rem" }}>
              • {scores.length} kilder scoret
              {scores.length > 0 && (
                <span> • Højeste: {Math.max(...scores.map(s => s.composite_score)).toFixed(0)}/100</span>
              )}
            </span>
          )}
        </p>
      )}

      <div style={{ marginTop: 12 }}>
        {sources.length === 0 ? (
          <p className="muted">Ingen kilder.</p>
        ) : viewMode === "cards" ? (
          <div>
            {sortedSources.map((s) => (
              <SourceCard
                key={s.source_id}
                source={s}
                score={scoreMap.get(s.source_id)}
                expanded={expandedId === s.source_id}
                onToggle={() => setExpandedId(expandedId === s.source_id ? null : s.source_id)}
              />
            ))}
          </div>
        ) : (
          <div style={{ overflow: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr>
                  <th align="left">Score</th>
                  <th align="left">source_id</th>
                  <th align="left">kind</th>
                  <th align="left">title/url/pmid</th>
                  <th align="left">år</th>
                  <th align="left">filer</th>
                </tr>
              </thead>
              <tbody>
                {sortedSources.map((s) => {
                  const score = scoreMap.get(s.source_id);
                  const scoreColor = score
                    ? score.composite_score >= 80
                      ? "#22c55e"
                      : score.composite_score >= 60
                      ? "#fbbf24"
                      : "#f87171"
                    : "#888";

                  return (
                    <tr key={s.source_id} style={{ borderTop: "1px solid #23314f" }}>
                      <td style={{ padding: "10px 0" }}>
                        {score ? (
                          <span style={{ color: scoreColor, fontWeight: "bold" }}>
                            {score.composite_score.toFixed(0)}
                          </span>
                        ) : (
                          <span className="muted">-</span>
                        )}
                      </td>
                      <td style={{ padding: "10px 0" }}>
                        <code>{s.source_id}</code>
                      </td>
                      <td className="muted" style={{ padding: "10px 0" }}>
                        {s.kind}
                      </td>
                      <td className="muted" style={{ padding: "10px 0" }}>
                        {s.title ?? s.url ?? s.pmid ?? "-"}
                      </td>
                      <td className="muted" style={{ padding: "10px 0" }}>
                        {score?.recency_year ?? s.year ?? "-"}
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
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
