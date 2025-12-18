import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import { useParams } from "react-router-dom";
import {
  apiEvidence,
  apiRun,
  apiSources,
  apiGetValidations,
  apiValidateRun,
  EvidenceReport,
  RunDetail,
  SourceRecord,
  ValidationResult,
} from "../api";

export default function RunPage() {
  const { runId } = useParams();
  const [run, setRun] = useState<RunDetail | null>(null);
  const [sources, setSources] = useState<SourceRecord[]>([]);
  const [evidence, setEvidence] = useState<EvidenceReport | null>(null);
  const [validations, setValidations] = useState<ValidationResult[]>([]);
  const [validating, setValidating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!runId) return;
    let cancelled = false;
    async function load(id: string) {
      try {
        const r = await apiRun(id);
        const s = await apiSources(id);
        const ev = await apiEvidence(id).catch(() => null);
        const v = await apiGetValidations(id).catch(() => ({ validations: [] }));
        if (!cancelled) {
          setRun(r);
          setSources(s.sources);
          setEvidence(ev);
          setValidations(v.validations);
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

  async function handleValidate() {
    if (!runId) return;
    setValidating(true);
    setError(null);
    try {
      const result = await apiValidateRun(runId);
      setValidations(result.validations);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setValidating(false);
    }
  }

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
              <a href={`/api/runs/${encodeURIComponent(runId)}/docx`} download>
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

        <h3 style={{ marginTop: 18 }}>Protokol-validering</h3>
        <p className="muted" style={{ marginBottom: "0.5rem" }}>
          Valider mod godkendte hospitalsprotokoller for at opdage konflikter.
        </p>
        {validations.length === 0 ? (
          <div>
            <p className="muted">Ingen validering foretaget.</p>
            <button onClick={handleValidate} disabled={validating || run?.status !== "DONE"}>
              {validating ? "Validerer..." : "Valider mod protokoller"}
            </button>
          </div>
        ) : (
          <div style={{ maxHeight: 300, overflow: "auto" }}>
            {validations.map((v) => (
              <div
                key={v.validation_id}
                style={{
                  padding: "0.75rem",
                  marginBottom: "0.5rem",
                  background: v.conflict_count > 0 ? "#451a03" : "#14532d",
                  border: v.conflict_count > 0 ? "1px solid #78350f" : "1px solid #166534",
                  borderRadius: "6px",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
                  <strong>{v.protocol_name}</strong>
                  <span
                    style={{
                      fontSize: "0.8rem",
                      padding: "0.2rem 0.5rem",
                      borderRadius: "9999px",
                      background: v.content_similarity >= 0.7 ? "#166534" : v.content_similarity >= 0.4 ? "#854d0e" : "#7f1d1d",
                      color: "#fff",
                    }}
                  >
                    {(v.content_similarity * 100).toFixed(0)}% match
                  </span>
                </div>

                {v.conflict_count > 0 ? (
                  <div>
                    <strong style={{ color: "#fca5a5" }}>
                      {v.conflict_count} konflikt{v.conflict_count !== 1 ? "er" : ""} fundet
                    </strong>
                    <ul style={{ margin: "0.5rem 0", paddingLeft: "1.25rem" }}>
                      {v.conflicts.map((c, i) => (
                        <li
                          key={i}
                          style={{
                            marginBottom: "0.5rem",
                            color: c.severity === "critical" ? "#fca5a5" : c.severity === "warning" ? "#fcd34d" : "#94a3b8",
                          }}
                        >
                          <span
                            style={{
                              fontSize: "0.7rem",
                              fontWeight: "600",
                              textTransform: "uppercase",
                              marginRight: "0.5rem",
                              padding: "0.1rem 0.3rem",
                              borderRadius: "4px",
                              background: c.severity === "critical" ? "#7f1d1d" : c.severity === "warning" ? "#78350f" : "#334155",
                            }}
                          >
                            {c.type}
                          </span>
                          <span className="muted">{c.section}:</span> {c.explanation}
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : (
                  <p style={{ color: "#86efac", margin: 0 }}>Ingen konflikter fundet</p>
                )}
              </div>
            ))}
            <button onClick={handleValidate} disabled={validating} style={{ marginTop: "0.5rem" }}>
              {validating ? "Validerer..." : "Valider igen"}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
