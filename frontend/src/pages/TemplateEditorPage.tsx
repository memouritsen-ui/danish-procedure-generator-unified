/**
 * Template Editor Page
 *
 * Create new templates or edit existing ones.
 * Allows adding/removing/reordering sections with format and bundle settings.
 */
import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { apiGetTemplate, apiCreateTemplate, apiUpdateTemplate, SectionConfig, TemplateConfig } from "../api";

export default function TemplateEditorPage() {
  const { templateId } = useParams();
  const navigate = useNavigate();
  const isNew = templateId === "new";

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [titlePrefix, setTitlePrefix] = useState("Procedure");
  const [sections, setSections] = useState<SectionConfig[]>([]);
  const [isSystem, setIsSystem] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(!isNew);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (isNew) {
      setSections([{ heading: "Indikationer", format: "bullets", bundle: "action" }]);
      return;
    }

    apiGetTemplate(templateId!)
      .then((data) => {
        setName(data.name);
        setDescription(data.description ?? "");
        setTitlePrefix(data.config.title_prefix);
        setSections(data.config.sections);
        setIsSystem(data.is_system);
        setLoading(false);
      })
      .catch((e) => {
        setError(e instanceof Error ? e.message : String(e));
        setLoading(false);
      });
  }, [templateId, isNew]);

  function addSection() {
    setSections([...sections, { heading: "", format: "bullets", bundle: "action" }]);
  }

  function removeSection(index: number) {
    setSections(sections.filter((_, i) => i !== index));
  }

  function updateSection(index: number, field: keyof SectionConfig, value: string) {
    const updated = [...sections];
    updated[index] = { ...updated[index], [field]: value } as SectionConfig;
    setSections(updated);
  }

  function moveSection(index: number, direction: "up" | "down") {
    const newIndex = direction === "up" ? index - 1 : index + 1;
    if (newIndex < 0 || newIndex >= sections.length) return;

    const updated = [...sections];
    [updated[index], updated[newIndex]] = [updated[newIndex], updated[index]];
    setSections(updated);
  }

  async function save() {
    if (!name.trim()) {
      setError("Navn er paakraevet");
      return;
    }

    if (sections.length === 0) {
      setError("Skabelonen skal have mindst én sektion");
      return;
    }

    if (sections.some((s) => !s.heading.trim())) {
      setError("Alle sektioner skal have et navn");
      return;
    }

    const config: TemplateConfig = { title_prefix: titlePrefix, sections };

    setSaving(true);
    setError(null);

    try {
      if (isNew) {
        await apiCreateTemplate(name, config, description || undefined);
      } else {
        await apiUpdateTemplate(templateId!, { name, description, config });
      }
      navigate("/templates");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="card">
        <h2>{isNew ? "Opret skabelon" : "Rediger skabelon"}</h2>
        <p className="muted">Indlaeser...</p>
      </div>
    );
  }

  return (
    <div className="card">
      <h2>{isNew ? "Opret skabelon" : isSystem ? "Vis skabelon" : "Rediger skabelon"}</h2>

      {error && (
        <div style={{ marginBottom: "1rem", padding: "0.75rem", background: "#fef2f2", borderRadius: "6px", color: "#dc2626" }}>
          Fejl: {error}
        </div>
      )}

      {isSystem && (
        <div style={{ marginBottom: "1rem", padding: "0.75rem", background: "#fffbeb", borderRadius: "6px", color: "#b45309" }}>
          System-skabeloner kan ikke redigeres. Du kan oprette en kopi ved at notere sektionerne og oprette en ny skabelon.
        </div>
      )}

      <div style={{ marginBottom: "1rem" }}>
        <label className="muted">Navn</label>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          disabled={isSystem}
          placeholder="Fx: Kirurgisk procedure"
          style={{ width: "100%" }}
        />
      </div>

      <div style={{ marginBottom: "1rem" }}>
        <label className="muted">Beskrivelse</label>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          disabled={isSystem}
          rows={2}
          placeholder="Kort beskrivelse af skabelonens formaal..."
          style={{ width: "100%" }}
        />
      </div>

      <div style={{ marginBottom: "1.5rem" }}>
        <label className="muted">Titel-praefiks</label>
        <input
          value={titlePrefix}
          onChange={(e) => setTitlePrefix(e.target.value)}
          disabled={isSystem}
          placeholder="Procedure"
          style={{ width: "100%" }}
        />
        <span className="muted" style={{ fontSize: "0.8rem" }}>
          Bruges som praefiks i procedure-titlen
        </span>
      </div>

      <h3>Sektioner</h3>
      <p className="muted" style={{ marginBottom: "1rem" }}>
        Definer de sektioner der skal genereres. Traek for at aendre raekkefoelge.
      </p>

      <div style={{ marginBottom: "1rem" }}>
        {sections.map((section, i) => (
          <div
            key={i}
            style={{
              display: "flex",
              gap: "0.5rem",
              alignItems: "center",
              padding: "0.75rem",
              marginBottom: "0.5rem",
              background: "#1e293b",
              border: "1px solid #334155",
              borderRadius: "6px",
            }}
          >
            <div style={{ flex: 2 }}>
              <input
                value={section.heading}
                onChange={(e) => updateSection(i, "heading", e.target.value)}
                disabled={isSystem}
                placeholder="Sektionsnavn"
                style={{ width: "100%" }}
              />
            </div>
            <div style={{ flex: 1 }}>
              <select
                value={section.format}
                onChange={(e) => updateSection(i, "format", e.target.value)}
                disabled={isSystem}
                style={{ width: "100%" }}
              >
                <option value="bullets">Bullets</option>
                <option value="numbered">Nummereret</option>
                <option value="paragraphs">Afsnit</option>
              </select>
            </div>
            <div style={{ flex: 1 }}>
              <select
                value={section.bundle}
                onChange={(e) => updateSection(i, "bundle", e.target.value)}
                disabled={isSystem}
                style={{ width: "100%" }}
              >
                <option value="action">Action</option>
                <option value="explanation">Forklaring</option>
                <option value="safety">Sikkerhed</option>
              </select>
            </div>
            {!isSystem && (
              <>
                <button
                  onClick={() => moveSection(i, "up")}
                  disabled={i === 0}
                  style={{ padding: "0.4rem 0.6rem", fontSize: "0.9rem" }}
                  title="Flyt op"
                >
                  ↑
                </button>
                <button
                  onClick={() => moveSection(i, "down")}
                  disabled={i === sections.length - 1}
                  style={{ padding: "0.4rem 0.6rem", fontSize: "0.9rem" }}
                  title="Flyt ned"
                >
                  ↓
                </button>
                <button
                  onClick={() => removeSection(i)}
                  style={{ padding: "0.4rem 0.6rem", fontSize: "0.9rem", background: "#dc2626", borderColor: "#dc2626" }}
                  title="Fjern sektion"
                >
                  ×
                </button>
              </>
            )}
          </div>
        ))}
      </div>

      {!isSystem && (
        <button onClick={addSection} style={{ marginBottom: "1.5rem" }}>
          + Tilfoej sektion
        </button>
      )}

      <div style={{ display: "flex", gap: "0.75rem", marginTop: "1rem" }}>
        {!isSystem && (
          <button onClick={save} disabled={saving}>
            {saving ? "Gemmer..." : "Gem"}
          </button>
        )}
        <button onClick={() => navigate("/templates")} style={{ background: "#64748b", borderColor: "#64748b" }}>
          {isSystem ? "Tilbage" : "Annuller"}
        </button>
      </div>
    </div>
  );
}
