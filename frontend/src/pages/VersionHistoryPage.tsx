/**
 * Version History Page
 *
 * Lists all procedures with multiple versions and shows version history.
 * Allows comparing versions via diff view.
 */
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  apiProcedures,
  apiProcedureVersions,
  ProceduresResponse,
  ProcedureVersionsResponse,
  VersionInfo,
} from "../api";

export default function VersionHistoryPage() {
  const [procedures, setProcedures] = useState<ProceduresResponse | null>(null);
  const [selectedProcedure, setSelectedProcedure] = useState<string | null>(null);
  const [versions, setVersions] = useState<ProcedureVersionsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // Load procedures on mount
  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const data = await apiProcedures();
        if (!cancelled) {
          setProcedures(data);
          // Auto-select first procedure with multiple versions
          if (data.procedures.length > 0) {
            setSelectedProcedure(data.procedures[0]);
          }
          setLoading(false);
        }
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : String(e));
          setLoading(false);
        }
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  // Load versions when procedure selected
  useEffect(() => {
    if (!selectedProcedure) return;
    let cancelled = false;

    async function load() {
      try {
        const data = await apiProcedureVersions(selectedProcedure!);
        if (!cancelled) {
          setVersions(data);
        }
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : String(e));
        }
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [selectedProcedure]);

  // Group versions by procedure for quick stats
  const versionStats = useMemo(() => {
    if (!versions) return null;
    return {
      total: versions.count,
      latest: versions.versions[0],
      oldest: versions.versions[versions.versions.length - 1],
    };
  }, [versions]);

  if (loading) {
    return (
      <div className="card">
        <h2>Versionshistorik</h2>
        <p className="muted">Indlaeser...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="card">
        <h2>Versionshistorik</h2>
        <p className="muted" style={{ color: "#f87171" }}>
          Fejl: {error}
        </p>
      </div>
    );
  }

  return (
    <div className="card">
      <h2>Versionshistorik</h2>

      {procedures && procedures.count === 0 ? (
        <p className="muted">Ingen procedurer med versioner fundet.</p>
      ) : (
        <>
          {/* Procedure selector */}
          <div style={{ marginBottom: "1rem" }}>
            <label className="muted">Vaelg procedure</label>
            <select
              value={selectedProcedure || ""}
              onChange={(e) => setSelectedProcedure(e.target.value)}
            >
              {procedures?.procedures.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          </div>

          {/* Version stats */}
          {versionStats && (
            <div
              style={{
                display: "flex",
                gap: "2rem",
                marginBottom: "1rem",
                padding: "0.75rem",
                background: "#f9fafb",
                borderRadius: "4px",
              }}
            >
              <div>
                <span className="muted">Versioner: </span>
                <strong>{versionStats.total}</strong>
              </div>
              {versionStats.latest && (
                <div>
                  <span className="muted">Seneste: </span>
                  <strong>v{versionStats.latest.version_number}</strong>
                  <span className="muted">
                    {" "}
                    ({versionStats.latest.created_at_utc.split("T")[0]})
                  </span>
                </div>
              )}
            </div>
          )}

          {/* Version list */}
          {versions && versions.versions.length > 0 && (
            <div style={{ marginTop: "1rem" }}>
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead>
                  <tr>
                    <th align="left">Version</th>
                    <th align="left">Dato</th>
                    <th align="left">Kvalitetsscore</th>
                    <th align="left">Note</th>
                    <th align="left">Handlinger</th>
                  </tr>
                </thead>
                <tbody>
                  {versions.versions.map((v, idx) => (
                    <VersionRow
                      key={v.run_id}
                      version={v}
                      previousVersion={versions.versions[idx + 1] ?? null}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}

interface VersionRowProps {
  version: VersionInfo;
  previousVersion: VersionInfo | null;
}

function VersionRow({ version, previousVersion }: VersionRowProps) {
  const dateStr = version.created_at_utc.split("T")[0];
  const scoreColor = version.quality_score
    ? version.quality_score >= 80
      ? "#22c55e"
      : version.quality_score >= 60
      ? "#fbbf24"
      : "#f87171"
    : "#888";

  return (
    <tr style={{ borderTop: "1px solid #e5e7eb" }}>
      <td style={{ padding: "0.75rem 0" }}>
        <strong>v{version.version_number}</strong>
        {version.parent_run_id && (
          <span className="muted" style={{ fontSize: "0.75rem", marginLeft: "0.5rem" }}>
            (baseret paa v{version.version_number - 1})
          </span>
        )}
      </td>
      <td className="muted" style={{ padding: "0.75rem 0" }}>
        {dateStr}
      </td>
      <td style={{ padding: "0.75rem 0" }}>
        {version.quality_score ? (
          <span style={{ color: scoreColor, fontWeight: "bold" }}>
            {version.quality_score}
          </span>
        ) : (
          <span className="muted">-</span>
        )}
      </td>
      <td className="muted" style={{ padding: "0.75rem 0", maxWidth: "200px" }}>
        {version.version_note || "-"}
      </td>
      <td style={{ padding: "0.75rem 0" }}>
        <Link
          to={`/runs/${version.run_id}`}
          style={{ marginRight: "1rem", color: "#3b82f6" }}
        >
          Vis
        </Link>
        {previousVersion && (
          <Link
            to={`/diff/${version.run_id}/${previousVersion.run_id}`}
            style={{ color: "#8b5cf6" }}
          >
            Sammenlign
          </Link>
        )}
      </td>
    </tr>
  );
}
