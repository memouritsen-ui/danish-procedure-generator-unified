/**
 * Protocols Page
 *
 * Manage hospital protocols for validation against generated procedures.
 * Upload, view, and delete protocols.
 */
import { useEffect, useRef, useState } from "react";
import { apiListProtocols, apiUploadProtocol, apiDeleteProtocol, Protocol } from "../api";

export default function ProtocolsPage() {
  const [protocols, setProtocols] = useState<Protocol[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Upload form state
  const [uploadName, setUploadName] = useState("");
  const [uploadDescription, setUploadDescription] = useState("");
  const [uploadVersion, setUploadVersion] = useState("");
  const [uploadApprovedBy, setUploadApprovedBy] = useState("");
  const [uploading, setUploading] = useState(false);

  // Filter state
  const [statusFilter, setStatusFilter] = useState<string>("active");

  async function loadProtocols() {
    try {
      setLoading(true);
      const data = await apiListProtocols(statusFilter);
      setProtocols(data.protocols);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadProtocols();
  }, [statusFilter]);

  async function handleUpload() {
    const file = fileInputRef.current?.files?.[0];
    if (!file || !uploadName.trim()) {
      setError("Vaelg en fil og angiv et navn");
      return;
    }

    setUploading(true);
    setError(null);

    try {
      await apiUploadProtocol(
        file,
        uploadName.trim(),
        uploadDescription.trim() || undefined,
        uploadVersion.trim() || undefined,
        uploadApprovedBy.trim() || undefined
      );

      // Reset form
      setUploadName("");
      setUploadDescription("");
      setUploadVersion("");
      setUploadApprovedBy("");
      if (fileInputRef.current) fileInputRef.current.value = "";

      await loadProtocols();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setUploading(false);
    }
  }

  async function handleDelete(protocolId: string) {
    if (!confirm("Er du sikker paa at du vil slette denne protokol?")) return;
    try {
      await apiDeleteProtocol(protocolId);
      await loadProtocols();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  if (loading && protocols.length === 0) {
    return (
      <div className="card">
        <h2>Protokol-bibliotek</h2>
        <p className="muted">Indlaeser...</p>
      </div>
    );
  }

  return (
    <div className="split">
      <div className="card">
        <h2>Protokol-bibliotek</h2>
        <p className="muted">
          Upload godkendte hospitalsprotkoller for validering mod genererede procedurer.
        </p>

        {error && (
          <div style={{ marginBottom: "1rem", padding: "0.75rem", background: "#fef2f2", borderRadius: "6px", color: "#dc2626" }}>
            Fejl: {error}
          </div>
        )}

        <div style={{ marginBottom: "1rem" }}>
          <label className="muted">Vis status</label>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            style={{ marginLeft: "0.5rem" }}
          >
            <option value="active">Aktive</option>
            <option value="archived">Arkiverede</option>
            <option value="draft">Udkast</option>
            <option value="all">Alle</option>
          </select>
        </div>

        <div style={{ marginBottom: "1rem" }}>
          {protocols.length === 0 ? (
            <p className="muted">Ingen protokoller endnu. Upload en protokol for at komme i gang.</p>
          ) : (
            protocols.map((p) => (
              <div
                key={p.protocol_id}
                style={{
                  padding: "1rem",
                  marginBottom: "0.75rem",
                  background: "#1e293b",
                  border: "1px solid #334155",
                  borderRadius: "6px",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                  <div>
                    <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.25rem" }}>
                      <strong style={{ fontSize: "1.1rem" }}>{p.name}</strong>
                      {p.version && (
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
                          v{p.version}
                        </span>
                      )}
                      <span
                        style={{
                          fontSize: "0.7rem",
                          fontWeight: "600",
                          color: p.status === "active" ? "#22c55e" : "#94a3b8",
                          background: p.status === "active" ? "#14532d" : "#334155",
                          padding: "0.1rem 0.4rem",
                          borderRadius: "9999px",
                        }}
                      >
                        {p.status}
                      </span>
                    </div>
                    <p className="muted" style={{ margin: "0.25rem 0" }}>
                      {p.description ?? "Ingen beskrivelse"}
                    </p>
                    <div className="muted" style={{ fontSize: "0.85rem" }}>
                      {p.approved_by && <span>Godkendt af: {p.approved_by} | </span>}
                      <span>Oprettet: {new Date(p.created_at_utc).toLocaleDateString("da-DK")}</span>
                    </div>
                  </div>

                  <div style={{ display: "flex", gap: "0.5rem" }}>
                    <button
                      onClick={() => handleDelete(p.protocol_id)}
                      style={{
                        padding: "0.4rem 0.8rem",
                        fontSize: "0.85rem",
                        background: "#dc2626",
                        borderColor: "#dc2626",
                      }}
                    >
                      Slet
                    </button>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      <div className="card">
        <h2>Upload protokol</h2>
        <p className="muted">
          Upload en PDF, DOCX eller TXT fil med en godkendt hospitalsprotokol.
        </p>

        <div style={{ marginBottom: "1rem" }}>
          <label className="muted">Fil (PDF, DOCX eller TXT) *</label>
          <input
            type="file"
            ref={fileInputRef}
            accept=".pdf,.docx,.doc,.txt"
            style={{ width: "100%" }}
          />
        </div>

        <div style={{ marginBottom: "1rem" }}>
          <label className="muted">Protokol-navn *</label>
          <input
            value={uploadName}
            onChange={(e) => setUploadName(e.target.value)}
            placeholder="Fx: Akut anafylaksi behandling"
            style={{ width: "100%" }}
          />
        </div>

        <div style={{ marginBottom: "1rem" }}>
          <label className="muted">Beskrivelse</label>
          <textarea
            value={uploadDescription}
            onChange={(e) => setUploadDescription(e.target.value)}
            rows={2}
            placeholder="Kort beskrivelse af protokollen..."
            style={{ width: "100%" }}
          />
        </div>

        <div style={{ display: "flex", gap: "1rem", marginBottom: "1rem" }}>
          <div style={{ flex: 1 }}>
            <label className="muted">Version</label>
            <input
              value={uploadVersion}
              onChange={(e) => setUploadVersion(e.target.value)}
              placeholder="2.0"
              style={{ width: "100%" }}
            />
          </div>
          <div style={{ flex: 1 }}>
            <label className="muted">Godkendt af</label>
            <input
              value={uploadApprovedBy}
              onChange={(e) => setUploadApprovedBy(e.target.value)}
              placeholder="Navn eller afdeling"
              style={{ width: "100%" }}
            />
          </div>
        </div>

        <button onClick={handleUpload} disabled={uploading}>
          {uploading ? "Uploader..." : "Upload protokol"}
        </button>
      </div>
    </div>
  );
}
