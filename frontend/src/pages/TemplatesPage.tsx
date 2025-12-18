/**
 * Templates Page
 *
 * Lists all available templates with management actions.
 * Allows setting default template and deleting custom templates.
 */
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { apiListTemplates, apiSetDefaultTemplate, apiDeleteTemplate, TemplateSummary } from "../api";

export default function TemplatesPage() {
  const [templates, setTemplates] = useState<TemplateSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  async function loadTemplates() {
    try {
      setLoading(true);
      const data = await apiListTemplates();
      setTemplates(data.templates);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadTemplates();
  }, []);

  async function handleSetDefault(templateId: string) {
    try {
      await apiSetDefaultTemplate(templateId);
      await loadTemplates();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function handleDelete(templateId: string) {
    if (!confirm("Er du sikker på at du vil slette denne skabelon?")) return;
    try {
      await apiDeleteTemplate(templateId);
      await loadTemplates();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  if (loading) {
    return (
      <div className="card">
        <h2>Skabeloner</h2>
        <p className="muted">Indlaeser...</p>
      </div>
    );
  }

  return (
    <div className="card">
      <h2>Skabeloner</h2>
      <p className="muted">
        Administrer procedure-skabeloner. Skabeloner bestemmer hvilke sektioner der genereres i en procedure.
      </p>

      {error && (
        <div style={{ marginBottom: "1rem", padding: "0.75rem", background: "#fef2f2", borderRadius: "6px", color: "#dc2626" }}>
          Fejl: {error}
        </div>
      )}

      <div style={{ marginBottom: "1.5rem" }}>
        <Link to="/templates/new">
          <button>+ Opret ny skabelon</button>
        </Link>
      </div>

      <div>
        {templates.map((t) => (
          <div
            key={t.template_id}
            style={{
              padding: "1rem",
              marginBottom: "0.75rem",
              background: t.is_default ? "#f0fdf4" : "#1e293b",
              border: t.is_default ? "1px solid #bbf7d0" : "1px solid #334155",
              borderRadius: "6px",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.25rem" }}>
                  <strong style={{ fontSize: "1.1rem" }}>{t.name}</strong>
                  {t.is_default && (
                    <span
                      style={{
                        fontSize: "0.7rem",
                        fontWeight: "600",
                        color: "#fff",
                        background: "#22c55e",
                        padding: "0.1rem 0.4rem",
                        borderRadius: "9999px",
                      }}
                    >
                      Standard
                    </span>
                  )}
                  {t.is_system && (
                    <span
                      style={{
                        fontSize: "0.7rem",
                        fontWeight: "600",
                        color: "#94a3b8",
                        background: "#334155",
                        padding: "0.1rem 0.4rem",
                        borderRadius: "9999px",
                      }}
                    >
                      System
                    </span>
                  )}
                </div>
                <p className="muted" style={{ margin: "0.25rem 0" }}>
                  {t.description ?? "Ingen beskrivelse"}
                </p>
                <p className="muted" style={{ margin: "0.25rem 0", fontSize: "0.85rem" }}>
                  {t.section_count} sektioner
                </p>
              </div>

              <div style={{ display: "flex", gap: "0.5rem" }}>
                <Link to={`/templates/${t.template_id}`}>
                  <button style={{ padding: "0.4rem 0.8rem", fontSize: "0.85rem" }}>
                    {t.is_system ? "Vis" : "Rediger"}
                  </button>
                </Link>
                {!t.is_default && (
                  <button
                    onClick={() => handleSetDefault(t.template_id)}
                    style={{ padding: "0.4rem 0.8rem", fontSize: "0.85rem" }}
                  >
                    Saet som standard
                  </button>
                )}
                {!t.is_system && (
                  <button
                    onClick={() => handleDelete(t.template_id)}
                    style={{
                      padding: "0.4rem 0.8rem",
                      fontSize: "0.85rem",
                      background: "#dc2626",
                      borderColor: "#dc2626",
                    }}
                  >
                    Slet
                  </button>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>

      {templates.length === 0 && (
        <p className="muted">Ingen skabeloner fundet. Opret en ny skabelon for at komme i gang.</p>
      )}
    </div>
  );
}
