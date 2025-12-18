import { useEffect, useState } from "react";
import {
  ApiKeyInfo,
  ApiKeyStatus,
  AppStatus,
  LibraryStats,
  apiAnthropicStatus,
  apiDeleteAnthropicKey,
  apiDeleteNcbiKey,
  apiDeleteOpenAiKey,
  apiGetAnthropicKey,
  apiGetConfig,
  apiGetNcbiKey,
  apiGetOpenAiKey,
  apiLibraryStats,
  apiNcbiStatus,
  apiOpenAiStatus,
  apiSetAnthropicKey,
  apiSetConfig,
  apiSetNcbiKey,
  apiSetOpenAiKey,
  apiStatus,
} from "../api";
import DocxTemplateEditor from "../components/DocxTemplateEditor";

export default function SettingsPage() {
  const [authorGuide, setAuthorGuide] = useState("");
  const [allowlist, setAllowlist] = useState("");
  const [docxTemplate, setDocxTemplate] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [savingDocx, setSavingDocx] = useState(false);
  const [statusInfo, setStatusInfo] = useState<AppStatus | null>(null);
  const [libraryStats, setLibraryStats] = useState<LibraryStats | null>(null);
  const [openAiInfo, setOpenAiInfo] = useState<ApiKeyInfo | null>(null);
  const [openAiKey, setOpenAiKey] = useState("");
  const [openAiStatus, setOpenAiStatus] = useState<ApiKeyStatus | null>(null);
  const [openAiBusy, setOpenAiBusy] = useState(false);
  const [ncbiInfo, setNcbiInfo] = useState<ApiKeyInfo | null>(null);
  const [ncbiKey, setNcbiKey] = useState("");
  const [ncbiStatus, setNcbiStatus] = useState<ApiKeyStatus | null>(null);
  const [ncbiBusy, setNcbiBusy] = useState(false);
  const [anthropicInfo, setAnthropicInfo] = useState<ApiKeyInfo | null>(null);
  const [anthropicKey, setAnthropicKey] = useState("");
  const [anthropicStatus, setAnthropicStatus] = useState<ApiKeyStatus | null>(null);
  const [anthropicBusy, setAnthropicBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [ag, al, dt, keyInfo, st, ninfo, ainfo, libStats] = await Promise.all([
          apiGetConfig("author_guide"),
          apiGetConfig("source_allowlist"),
          apiGetConfig("docx_template").catch(() => ""),
          apiGetOpenAiKey(),
          apiStatus(),
          apiGetNcbiKey(),
          apiGetAnthropicKey(),
          apiLibraryStats().catch(() => null),
        ]);
        if (!cancelled) {
          setAuthorGuide(ag);
          setAllowlist(al);
          setDocxTemplate(dt);
          setOpenAiInfo(keyInfo);
          setStatusInfo(st);
          setNcbiInfo(ninfo);
          setAnthropicInfo(ainfo);
          setLibraryStats(libStats);
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  async function onSave() {
    setError(null);
    setSaving(true);
    try {
      await apiSetConfig("author_guide", authorGuide);
      await apiSetConfig("source_allowlist", allowlist);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  }

  async function onSaveDocxTemplate() {
    if (!docxTemplate) return;
    setError(null);
    setSavingDocx(true);
    try {
      await apiSetConfig("docx_template", docxTemplate);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSavingDocx(false);
    }
  }

  async function onSaveOpenAiKey() {
    const key = openAiKey.trim();
    if (!key) return;
    setError(null);
    setOpenAiBusy(true);
    try {
      const info = await apiSetOpenAiKey(key);
      setOpenAiInfo(info);
      setOpenAiKey("");
      setOpenAiStatus(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setOpenAiBusy(false);
    }
  }

  async function onDeleteOpenAiKey() {
    setError(null);
    setOpenAiBusy(true);
    try {
      const info = await apiDeleteOpenAiKey();
      setOpenAiInfo(info);
      setOpenAiStatus(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setOpenAiBusy(false);
    }
  }

  async function onTestOpenAiKey() {
    setError(null);
    setOpenAiBusy(true);
    try {
      const status = await apiOpenAiStatus();
      setOpenAiStatus(status);
      setOpenAiInfo(await apiGetOpenAiKey());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setOpenAiBusy(false);
    }
  }

  async function onSaveNcbiKey() {
    const key = ncbiKey.trim();
    if (!key) return;
    setError(null);
    setNcbiBusy(true);
    try {
      const info = await apiSetNcbiKey(key);
      setNcbiInfo(info);
      setNcbiKey("");
      setNcbiStatus(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setNcbiBusy(false);
    }
  }

  async function onDeleteNcbiKey() {
    setError(null);
    setNcbiBusy(true);
    try {
      const info = await apiDeleteNcbiKey();
      setNcbiInfo(info);
      setNcbiStatus(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setNcbiBusy(false);
    }
  }

  async function onTestNcbiKey() {
    setError(null);
    setNcbiBusy(true);
    try {
      const status = await apiNcbiStatus();
      setNcbiStatus(status);
      setNcbiInfo(await apiGetNcbiKey());
      setStatusInfo(await apiStatus());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setNcbiBusy(false);
    }
  }

  async function onSaveAnthropicKey() {
    const key = anthropicKey.trim();
    if (!key) return;
    setError(null);
    setAnthropicBusy(true);
    try {
      const info = await apiSetAnthropicKey(key);
      setAnthropicInfo(info);
      setAnthropicKey("");
      setAnthropicStatus(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setAnthropicBusy(false);
    }
  }

  async function onDeleteAnthropicKey() {
    setError(null);
    setAnthropicBusy(true);
    try {
      const info = await apiDeleteAnthropicKey();
      setAnthropicInfo(info);
      setAnthropicStatus(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setAnthropicBusy(false);
    }
  }

  async function onTestAnthropicKey() {
    setError(null);
    setAnthropicBusy(true);
    try {
      const status = await apiAnthropicStatus();
      setAnthropicStatus(status);
      setAnthropicInfo(await apiGetAnthropicKey());
      setStatusInfo(await apiStatus());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setAnthropicBusy(false);
    }
  }

  return (
    <div className="card">
      <h2>Indstillinger</h2>
      <p className="muted">Redigér YAML direkte og gem via API.</p>
      {error && <p className="muted">{error}</p>}
      <div className="split" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
        <div>
          <h3>author_guide.yaml</h3>
          <textarea value={authorGuide} onChange={(e) => setAuthorGuide(e.target.value)} rows={18} />
        </div>
        <div>
          <h3>source_allowlist.yaml</h3>
          <textarea value={allowlist} onChange={(e) => setAllowlist(e.target.value)} rows={18} />
        </div>
      </div>
      <div style={{ marginTop: 12 }}>
        <button disabled={saving} onClick={onSave}>
          {saving ? "Gemmer…" : "Gem YAML filer"}
        </button>
      </div>

      <div style={{ marginTop: 24 }} className="card">
        <h3>DOCX Skabelon</h3>
        <p className="muted">Konfigurér sektioner, styling og indholdsformater for DOCX-output.</p>
        <DocxTemplateEditor
          yamlText={docxTemplate}
          onChange={setDocxTemplate}
          onSave={onSaveDocxTemplate}
          saving={savingDocx}
        />
      </div>

      {statusInfo && (
        <div style={{ marginTop: 18 }} className="card">
          <h3>Runtime</h3>
          <p className="muted">
            Backend v<code>{statusInfo.version}</code> · LLM provider: <code>{statusInfo.llm_provider}</code> · Model:{" "}
            <code>{statusInfo.llm_model}</code> · Embeddings: <code>{statusInfo.openai_embeddings_model}</code>
          </p>
          <p className="muted">
            LLM aktiv: <code>{statusInfo.use_llm ? "ja" : "nej"}</code> · Dummy mode:{" "}
            <code>{statusInfo.dummy_mode ? "ja" : "nej"}</code>
          </p>
          <p className="muted">
            OpenAI base URL: <code>{statusInfo.openai_base_url}</code> · Key source:{" "}
            <code>{statusInfo.openai_key_source}</code>
          </p>
          <p className="muted">
            Anthropic key source: <code>{statusInfo.anthropic_key_source}</code> · Ollama URL:{" "}
            <code>{statusInfo.ollama_base_url}</code>
          </p>
          <p className="muted">
            NCBI tool: <code>{statusInfo.ncbi_tool}</code> · email: <code>{statusInfo.ncbi_email ?? "-"}</code> · API
            key source: <code>{statusInfo.ncbi_api_key_source}</code>
          </p>
        </div>
      )}

      {libraryStats && (
        <div style={{ marginTop: 18 }} className="card">
          <h3>Danish Guideline Library</h3>
          <p className="muted">
            Status: <code>{libraryStats.available ? "tilgængelig" : "ikke tilgængelig"}</code> · Dokumenter:{" "}
            <code>{libraryStats.document_count.toLocaleString()}</code>
          </p>
          {libraryStats.available && Object.keys(libraryStats.source_stats).length > 0 && (
            <>
              <p className="muted" style={{ marginTop: 8 }}>Kilder:</p>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "4px", marginTop: 4 }}>
                {Object.entries(libraryStats.source_stats)
                  .sort((a, b) => b[1] - a[1])
                  .slice(0, 12)
                  .map(([source, count]) => (
                    <span key={source} className="muted" style={{ fontSize: "0.85em" }}>
                      <code>{source}</code>: {count.toLocaleString()}
                    </span>
                  ))}
              </div>
              <p className="muted" style={{ marginTop: 8, fontSize: "0.85em" }}>
                Sti: <code>{libraryStats.library_path}</code>
              </p>
            </>
          )}
        </div>
      )}

      <div style={{ marginTop: 18 }} className="card">
        <h3>API keys</h3>
        <p className="muted">
          OpenAI key:{" "}
          {openAiInfo?.present ? <code>{openAiInfo.masked ?? "configured"}</code> : <span>ikke sat</span>}
        </p>
        <div className="row" style={{ alignItems: "center" }}>
          <div style={{ flex: 1 }}>
            <label className="muted">Ny OpenAI API key</label>
            <input
              type="password"
              value={openAiKey}
              onChange={(e) => setOpenAiKey(e.target.value)}
              placeholder="sk-…"
            />
          </div>
        </div>
        <div className="row" style={{ marginTop: 12, alignItems: "center" }}>
          <button disabled={openAiBusy || !openAiKey.trim()} onClick={onSaveOpenAiKey}>
            Gem key
          </button>
          <button disabled={openAiBusy || !openAiInfo?.present} onClick={onDeleteOpenAiKey}>
            Fjern key
          </button>
          <button disabled={openAiBusy} onClick={onTestOpenAiKey}>
            Test forbindelse
          </button>
          {openAiBusy && <span className="muted">Arbejder…</span>}
        </div>
        {openAiStatus && (
          <p className="muted" style={{ marginTop: 10, whiteSpace: "pre-wrap" }}>
            Forbindelse: {openAiStatus.ok ? "OK" : "FEJL"} — {openAiStatus.message}
          </p>
        )}
        <p className="muted" style={{ marginTop: 10 }}>
          Nøglen gemmes lokalt i appens SQLite database under <code>data/index</code>.
        </p>

        <hr style={{ borderColor: "#23314f", marginTop: 18, marginBottom: 18 }} />

        <p className="muted">
          NCBI API key: {ncbiInfo?.present ? <code>{ncbiInfo.masked ?? "configured"}</code> : <span>ikke sat</span>}
        </p>
        <div className="row" style={{ alignItems: "center" }}>
          <div style={{ flex: 1 }}>
            <label className="muted">Ny NCBI API key</label>
            <input
              type="password"
              value={ncbiKey}
              onChange={(e) => setNcbiKey(e.target.value)}
              placeholder="NCBI key"
            />
          </div>
        </div>
        <div className="row" style={{ marginTop: 12, alignItems: "center" }}>
          <button disabled={ncbiBusy || !ncbiKey.trim()} onClick={onSaveNcbiKey}>
            Gem key
          </button>
          <button disabled={ncbiBusy || !ncbiInfo?.present} onClick={onDeleteNcbiKey}>
            Fjern key
          </button>
          <button disabled={ncbiBusy} onClick={onTestNcbiKey}>
            Test forbindelse
          </button>
          {ncbiBusy && <span className="muted">Arbejder…</span>}
        </div>
        {ncbiStatus && (
          <p className="muted" style={{ marginTop: 10, whiteSpace: "pre-wrap" }}>
            Forbindelse: {ncbiStatus.ok ? "OK" : "FEJL"} — {ncbiStatus.message}
          </p>
        )}

        <hr style={{ borderColor: "#23314f", marginTop: 18, marginBottom: 18 }} />

        <p className="muted">
          Anthropic API key:{" "}
          {anthropicInfo?.present ? <code>{anthropicInfo.masked ?? "configured"}</code> : <span>ikke sat</span>}
        </p>
        <div className="row" style={{ alignItems: "center" }}>
          <div style={{ flex: 1 }}>
            <label className="muted">Ny Anthropic API key</label>
            <input
              type="password"
              value={anthropicKey}
              onChange={(e) => setAnthropicKey(e.target.value)}
              placeholder="sk-ant-…"
            />
          </div>
        </div>
        <div className="row" style={{ marginTop: 12, alignItems: "center" }}>
          <button disabled={anthropicBusy || !anthropicKey.trim()} onClick={onSaveAnthropicKey}>
            Gem key
          </button>
          <button disabled={anthropicBusy || !anthropicInfo?.present} onClick={onDeleteAnthropicKey}>
            Fjern key
          </button>
          <button disabled={anthropicBusy} onClick={onTestAnthropicKey}>
            Test forbindelse
          </button>
          {anthropicBusy && <span className="muted">Arbejder…</span>}
        </div>
        {anthropicStatus && (
          <p className="muted" style={{ marginTop: 10, whiteSpace: "pre-wrap" }}>
            Forbindelse: {anthropicStatus.ok ? "OK" : "FEJL"} — {anthropicStatus.message}
          </p>
        )}
      </div>
    </div>
  );
}
