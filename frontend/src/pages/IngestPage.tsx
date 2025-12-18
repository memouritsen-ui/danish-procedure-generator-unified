import { useState } from "react";
import { apiIngestDocx, apiIngestPdf, apiIngestUrl } from "../api";

export default function IngestPage() {
  const [url, setUrl] = useState("");
  const [pdf, setPdf] = useState<File | null>(null);
  const [docx, setDocx] = useState<File | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function onIngestUrl() {
    setError(null);
    setMessage(null);
    try {
      const id = await apiIngestUrl(url.trim());
      setMessage(`Ingested URL. source_id=${id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function onIngestPdf() {
    if (!pdf) return;
    setError(null);
    setMessage(null);
    try {
      const id = await apiIngestPdf(pdf);
      setMessage(`Ingested PDF. source_id=${id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function onIngestDocx() {
    if (!docx) return;
    setError(null);
    setMessage(null);
    try {
      const id = await apiIngestDocx(docx);
      setMessage(`Ingested DOCX. source_id=${id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <div className="card">
      <h2>Ingest</h2>
      <p className="muted">Upload PDF/DOCX eller ingest en URL (kun allowlist).</p>

      {message && <p className="muted">{message}</p>}
      {error && <p className="muted">{error}</p>}

      <div className="split" style={{ marginTop: 12 }}>
        <div className="card">
          <h3>URL</h3>
          <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://…" />
          <div style={{ marginTop: 12 }}>
            <button onClick={onIngestUrl} disabled={!url.trim()}>
              Ingest URL
            </button>
          </div>
        </div>

        <div className="card">
          <h3>Filer</h3>
          <label className="muted">PDF</label>
          <input type="file" accept="application/pdf" onChange={(e) => setPdf(e.target.files?.[0] ?? null)} />
          <div style={{ marginTop: 12 }}>
            <button onClick={onIngestPdf} disabled={!pdf}>
              Upload PDF
            </button>
          </div>
          <hr style={{ borderColor: "#23314f", marginTop: 16, marginBottom: 16 }} />
          <label className="muted">DOCX</label>
          <input
            type="file"
            accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            onChange={(e) => setDocx(e.target.files?.[0] ?? null)}
          />
          <div style={{ marginTop: 12 }}>
            <button onClick={onIngestDocx} disabled={!docx}>
              Upload DOCX
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
