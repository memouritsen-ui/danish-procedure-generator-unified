import { useState, useEffect, useCallback } from "react";

interface StyleProfile {
  id: string;
  name: string;
  description: string | null;
  is_default: boolean;
  tone_config?: {
    tone_description?: string;
    target_audience?: string;
    detail_level?: string;
  };
  original_prompt?: string;
}

export function StylesPage() {
  const [styles, setStyles] = useState<StyleProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [newPrompt, setNewPrompt] = useState("");
  const [creating, setCreating] = useState(false);

  const fetchStyles = useCallback(async () => {
    try {
      const response = await fetch("/api/styles");
      if (!response.ok) throw new Error("Failed to fetch styles");
      const data = await response.json();
      setStyles(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStyles();
  }, [fetchStyles]);

  const handleCreate = async () => {
    if (!newPrompt.trim()) return;
    setCreating(true);

    try {
      // Create with the prompt as tone_description
      const createResponse = await fetch("/api/styles", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: "Ny Stil",
          tone_description: newPrompt,
          original_prompt: newPrompt,
        }),
      });
      if (!createResponse.ok) throw new Error("Failed to create style");

      setNewPrompt("");
      fetchStyles();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Creation failed");
    } finally {
      setCreating(false);
    }
  };

  const handleSetDefault = async (styleId: string) => {
    try {
      await fetch(`/api/styles/${styleId}/set-default`, { method: "POST" });
      fetchStyles();
    } catch (err) {
      setError("Failed to set default");
    }
  };

  const handleDelete = async (styleId: string) => {
    if (!confirm("Er du sikker på at du vil slette denne stil?")) return;
    try {
      await fetch(`/api/styles/${styleId}`, { method: "DELETE" });
      fetchStyles();
    } catch (err) {
      setError("Failed to delete");
    }
  };

  if (loading) return <div className="card">Indlæser stilprofiler...</div>;
  if (error) return <div className="card error">{error}</div>;

  return (
    <div>
      <h1>Stilprofiler</h1>

      <div className="card">
        <h2>Opret ny stil</h2>
        <p className="muted">
          Beskriv din ønskede stil med naturligt sprog. F.eks.: "Skriv som en
          dansk medicinsk lærebog til medicinstuderende. Formel tone, brug
          passiv form."
        </p>
        <textarea
          value={newPrompt}
          onChange={(e) => setNewPrompt(e.target.value)}
          placeholder="Beskriv din ønskede stil..."
          rows={4}
          style={{ width: "100%", marginBottom: 12 }}
        />
        <button onClick={handleCreate} disabled={creating || !newPrompt.trim()}>
          {creating ? "Opretter..." : "Opret Stil"}
        </button>
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <h2>Gemte stilprofiler</h2>
        {styles.length === 0 ? (
          <p className="muted">Ingen stilprofiler endnu.</p>
        ) : (
          <div>
            {styles.map((style) => (
              <div
                key={style.id}
                style={{
                  padding: 12,
                  border: "1px solid #ddd",
                  marginBottom: 8,
                  borderRadius: 4,
                  background: style.is_default ? "#f0f7ff" : "white",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <div>
                    <strong>{style.name}</strong>
                    {style.is_default && (
                      <span
                        style={{
                          marginLeft: 8,
                          background: "#0066cc",
                          color: "white",
                          padding: "2px 6px",
                          borderRadius: 3,
                          fontSize: 12,
                        }}
                      >
                        Standard
                      </span>
                    )}
                  </div>
                  <div>
                    {!style.is_default && (
                      <button
                        onClick={() => handleSetDefault(style.id)}
                        style={{ marginRight: 8 }}
                      >
                        Sæt som standard
                      </button>
                    )}
                    <button
                      onClick={() => handleDelete(style.id)}
                      style={{ background: "#cc0000", color: "white" }}
                    >
                      Slet
                    </button>
                  </div>
                </div>
                {style.tone_config?.tone_description && (
                  <p className="muted" style={{ marginTop: 8 }}>
                    {style.tone_config.tone_description}
                  </p>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
