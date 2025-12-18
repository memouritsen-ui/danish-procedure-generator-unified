import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import { useParams } from "react-router-dom";
import { apiEvidence, apiRun, apiSources, EvidenceReport, RunDetail, SourceRecord } from "../api";

export default function RunPage() {
  const { runId } = useParams();
  const [run, setRun] = useState<RunDetail | null>(null);
  const [sources, setSources] = useState<SourceRecord[]>([]);
  const [evidence, setEvidence] = useState<EvidenceReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!runId) return;
    let cancelled = false;
    async function load(id: string) {
      try {
        const r = await apiRun(id);
        const s = await apiSources(id);
        const ev = await apiEvidence(id).catch(() => null);
        if (!cancelled) {
          setRun(r);
          setSources(s.sources);
          setEvidence(ev);
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      }
    }
    void load(runId);
    return () => {
      cancelled = true;
    };
  }, [runId]);

  if (!runId) return <div className="card">Missing run_id</div>;

  return (
    <div className="split">
      <div className="card">
        <h2>Run</h2>
        {error && <p className="muted">{error}</p>}
        {run ? (
          <>
            <div className="muted">
              run_id: <code>{run.run_id}</code>
            </div>
            <div className="muted">Status: {run.status}</div>
            {run.quality_score != null && (
              <div className="muted">
                Kvalitet:{" "}
                <span style={{ color: run.quality_score >= 8 ? "#4ade80" : run.quality_score >= 6 ? "#fbbf24" : "#f87171" }}>
                  {run.quality_score}/10
                </span>
                {run.iterations_used != null && ` (${run.iterations_used} iteration${run.iterations_used !== 1 ? "er" : ""})`}
              </div>
            )}
            {run.total_cost_usd != null && run.total_cost_usd > 0 && (
              <div className="muted">
                Omkostning: ${run.total_cost_usd.toFixed(4)}
                {(run.total_input_tokens != null || run.total_output_tokens != null) && (
                  <span> ({run.total_input_tokens ?? 0} in / {run.total_output_tokens ?? 0} out tokens)</span>
                )}
              </div>
            )}
            {run.source_count != null && <div className="muted">Kilder: {run.source_count}</div>}
            {run.warnings && run.warnings.length > 0 && (
              <div style={{ marginTop: 12 }} className="card">
                <strong>Advarsler</strong>
                <div className="muted" style={{ whiteSpace: "pre-wrap" }}>
                  {run.warnings.join("\n")}
                </div>
              </div>
            )}
            {run.error && (
              <div style={{ marginTop: 12 }} className="card">
                <strong>Fejl</strong>
                <div className="muted" style={{ whiteSpace: "pre-wrap" }}>
                  {run.error}
                </div>
              </div>
            )}
            <div style={{ marginTop: 12 }}>
              <a href={`/api/runs/${encodeURIComponent(runId)}/docx`}>
                <button>Download DOCX</button>
              </a>
            </div>
            <div style={{ marginTop: 12 }} className="row">
              <a href={`/api/runs/${encodeURIComponent(runId)}/bundle`}>
                <button>Download bundle</button>
              </a>
              <a
                className="muted"
                href={`/api/runs/${encodeURIComponent(runId)}/manifest`}
                target="_blank"
                rel="noreferrer"
              >
                Manifest (JSON)
              </a>
              {" · "}
              <a
                className="muted"
                href={`/api/runs/${encodeURIComponent(runId)}/evidence`}
                target="_blank"
                rel="noreferrer"
              >
                Evidence (JSON)
              </a>
            </div>
          </>
        ) : (
          <p className="muted">Loader…</p>
        )}
      </div>

      <div className="card">
        <h2>Output</h2>
        {run?.procedure_md ? (
          <div style={{ maxHeight: 520, overflow: "auto" }}>
            <ReactMarkdown>{run.procedure_md}</ReactMarkdown>
          </div>
        ) : (
          <p className="muted">Ingen output.</p>
        )}

        {evidence && (
          <div style={{ marginTop: 18 }} className="card">
            <h3>Evidens-check</h3>
            <p className="muted">
              Understøttet: {evidence.supported_count}/{evidence.sentence_count} · Mangler:{" "}
              {evidence.unsupported_count}
            </p>
            {evidence.unsupported_count > 0 && (
              <div style={{ maxHeight: 220, overflow: "auto" }}>
                {evidence.sentences
                  .filter((x) => !x.supported)
                  .slice(0, 20)
                  .map((x, idx) => {
                    const best = [...x.matches].sort((a, b) => b.bm25 - a.bm25)[0];
                    const excerpt = best?.snippet?.excerpt ?? null;
                    return (
                      <div key={`${x.line_no}-${idx}`} style={{ padding: "10px 0", borderBottom: "1px solid #23314f" }}>
                        <div className="muted">
                          Linje {x.line_no}: <code>{x.citations.join(", ")}</code>
                        </div>
                        <div style={{ marginTop: 6 }}>{x.text}</div>
                        {best && excerpt && (
                          <div className="muted" style={{ marginTop: 6, fontSize: 12 }}>
                            Bedste match: <code>{best.source_id}</code> (bm25 {best.bm25.toFixed(2)}, overlap{" "}
                            {best.overlap}) — {excerpt}…
                          </div>
                        )}
                      </div>
                    );
                  })}
              </div>
            )}
          </div>
        )}

        <h3 style={{ marginTop: 18 }}>Kilder</h3>
        {sources.length === 0 ? (
          <p className="muted">Ingen kilder.</p>
        ) : (
          <div style={{ maxHeight: 220, overflow: "auto" }}>
            {sources.map((s) => (
              <div key={s.source_id} style={{ padding: "10px 0", borderBottom: "1px solid #23314f" }}>
                <div>
                  <strong>{s.source_id}</strong> <span className="muted">({s.kind})</span>
                </div>
                <div className="muted">{s.title ?? s.url ?? s.pmid ?? "-"}</div>
                <div className="muted" style={{ marginTop: 6, fontSize: 12 }}>
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
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
