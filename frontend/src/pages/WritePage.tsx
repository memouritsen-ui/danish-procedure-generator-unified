import { useEffect, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import { apiRun, apiSources, apiWrite, apiListTemplates, RunDetail, SourceRecord, TemplateSummary } from "../api";

type Status = "idle" | "running" | "done" | "failed";

export default function WritePage() {
  const [procedure, setProcedure] = useState("");
  const [context, setContext] = useState("");
  const [runId, setRunId] = useState<string | null>(null);
  const [status, setStatus] = useState<Status>("idle");
  const [run, setRun] = useState<RunDetail | null>(null);
  const [sources, setSources] = useState<SourceRecord[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [templates, setTemplates] = useState<TemplateSummary[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState<string | null>(null);

  // Load templates on mount
  useEffect(() => {
    apiListTemplates()
      .then((data) => {
        setTemplates(data.templates);
        // Select default template
        const defaultTemplate = data.templates.find((t) => t.is_default);
        if (defaultTemplate) {
          setSelectedTemplate(defaultTemplate.template_id);
        }
      })
      .catch((e) => console.error("Failed to load templates:", e));
  }, []);

  const canGenerate = useMemo(() => procedure.trim().length > 0 && status !== "running", [procedure, status]);

  async function onGenerate() {
    setError(null);
    setRun(null);
    setSources([]);
    setStatus("running");
    try {
      const id = await apiWrite({
        procedure: procedure.trim(),
        context: context.trim() || undefined,
        template_id: selectedTemplate ?? undefined,
      });
      setRunId(id);
    } catch (e) {
      setStatus("failed");
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  useEffect(() => {
    if (!runId) return;
    const id = runId;
    let cancelled = false;
    let timeoutId: number | undefined;

    async function poll() {
      try {
        const r = await apiRun(id);
        if (cancelled) return;
        setRun(r);
        if (r.status === "DONE") {
          setStatus("done");
          const s = await apiSources(id);
          if (!cancelled) setSources(s.sources);
          return;
        }
        if (r.status === "FAILED") {
          setStatus("failed");
          setError(r.error ?? "Run failed");
          return;
        }
        setStatus("running");
        timeoutId = window.setTimeout(poll, 1200);
      } catch (e) {
        if (cancelled) return;
        setStatus("failed");
        setError(e instanceof Error ? e.message : String(e));
      }
    }

    void poll();

    return () => {
      cancelled = true;
      if (timeoutId) window.clearTimeout(timeoutId);
    };
  }, [runId]);

  return (
    <div className="split">
      <div className="card">
        <h2>Skriv procedure</h2>
        <p className="muted">Angiv procedure-navn og evt. kontekst. Systemet kører som en background job.</p>
        <div className="row">
          <div style={{ flex: 1 }}>
            <label className="muted">Procedure</label>
            <input value={procedure} onChange={(e) => setProcedure(e.target.value)} placeholder="Fx: Akut astma" />
          </div>
        </div>
        <div style={{ marginTop: 12 }}>
          <label className="muted">Kontekst (valgfri)</label>
          <textarea
            value={context}
            onChange={(e) => setContext(e.target.value)}
            rows={6}
            placeholder="Fx: voksne, præhospitalt, særlige constraints…"
          />
        </div>
        <div style={{ marginTop: 12 }}>
          <label className="muted">Skabelon</label>
          <select
            value={selectedTemplate ?? ""}
            onChange={(e) => setSelectedTemplate(e.target.value || null)}
            style={{ width: "100%" }}
          >
            {templates.map((t) => (
              <option key={t.template_id} value={t.template_id}>
                {t.name} {t.is_default ? "(standard)" : ""} - {t.section_count} sektioner
              </option>
            ))}
          </select>
          {selectedTemplate && (
            <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>
              {templates.find((t) => t.template_id === selectedTemplate)?.description ?? ""}
            </div>
          )}
        </div>
        <div className="row" style={{ marginTop: 12, alignItems: "center" }}>
          <button disabled={!canGenerate} onClick={onGenerate}>
            Generér
          </button>
          <span className="muted">
            Status:{" "}
            {status === "idle"
              ? "Klar"
              : status === "running"
                ? "Kører…"
                : status === "done"
                  ? "DONE"
                  : "FAILED"}
          </span>
        </div>
        {error && (
          <div style={{ marginTop: 12 }} className="card">
            <strong>Fejl</strong>
            <div className="muted" style={{ whiteSpace: "pre-wrap" }}>
              {error}
            </div>
          </div>
        )}
        {runId && (
          <div style={{ marginTop: 12 }} className="muted">
            run_id: <code>{runId}</code>
          </div>
        )}
        {runId && status === "done" && (
          <div style={{ marginTop: 12 }} className="row">
            <a href={`/api/runs/${encodeURIComponent(runId)}/docx`} download>
              <button>Download DOCX</button>
            </a>
          </div>
        )}
      </div>

      <div className="card">
        <h2>Preview</h2>
        {!run?.procedure_md ? (
          <p className="muted">Ingen output endnu.</p>
        ) : (
          <div style={{ maxHeight: 520, overflow: "auto" }}>
            <ReactMarkdown>{run.procedure_md}</ReactMarkdown>
          </div>
        )}

        <h3 style={{ marginTop: 18 }}>Kilder</h3>
        {sources.length === 0 ? (
          <p className="muted">Ingen kilder at vise.</p>
        ) : (
          <div style={{ maxHeight: 220, overflow: "auto" }}>
            {sources.map((s) => (
              <div key={s.source_id} style={{ padding: "10px 0", borderBottom: "1px solid #23314f" }}>
                <div>
                  <strong>{s.source_id}</strong> <span className="muted">({s.kind})</span>
                </div>
                <div className="muted">{s.title ?? s.url ?? s.pmid ?? "-"}</div>
                <div className="muted" style={{ fontSize: 12 }}>
                  raw_sha256: <code>{s.raw_sha256.slice(0, 16)}…</code> · normalized_sha256:{" "}
                  <code>{s.normalized_sha256.slice(0, 16)}…</code>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
