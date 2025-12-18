/**
 * Diff Page
 *
 * Shows structural diff between two procedure versions.
 * Displays section-by-section comparison with added/removed/modified indicators.
 */
import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { apiDiff, VersionDiff, SectionDiff } from "../api";

export default function DiffPage() {
  const { runId, otherRunId } = useParams<{ runId: string; otherRunId: string }>();
  const [diff, setDiff] = useState<VersionDiff | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (!runId || !otherRunId) return;
    let cancelled = false;

    async function load() {
      try {
        const data = await apiDiff(runId!, otherRunId!);
        if (!cancelled) {
          setDiff(data);
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
  }, [runId, otherRunId]);

  const toggleSection = (heading: string) => {
    setExpandedSections((prev) => {
      const next = new Set(prev);
      if (next.has(heading)) {
        next.delete(heading);
      } else {
        next.add(heading);
      }
      return next;
    });
  };

  if (loading) {
    return (
      <div className="card">
        <h2>Sammenligning</h2>
        <p className="muted">Indlaeser diff...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="card">
        <h2>Sammenligning</h2>
        <p className="muted" style={{ color: "#f87171" }}>
          Fejl: {error}
        </p>
      </div>
    );
  }

  if (!diff) {
    return (
      <div className="card">
        <h2>Sammenligning</h2>
        <p className="muted">Ingen data fundet.</p>
      </div>
    );
  }

  return (
    <div className="card">
      <div style={{ marginBottom: "1rem" }}>
        <Link to="/versions" style={{ color: "#3b82f6" }}>
          &larr; Tilbage til versioner
        </Link>
      </div>

      <h2>
        Sammenligning: v{diff.old_version} &rarr; v{diff.new_version}
      </h2>

      <p className="muted" style={{ marginBottom: "1rem" }}>
        {diff.procedure}
      </p>

      {/* Summary */}
      <div
        style={{
          display: "flex",
          gap: "1.5rem",
          marginBottom: "1.5rem",
          padding: "1rem",
          background: diff.has_changes ? "#f0fdf4" : "#f9fafb",
          borderRadius: "6px",
          border: diff.has_changes ? "1px solid #bbf7d0" : "1px solid #e5e7eb",
        }}
      >
        <div>
          <span className="muted">Status: </span>
          <strong>{diff.has_changes ? diff.summary : "Ingen aendringer"}</strong>
        </div>
        {diff.sections_added > 0 && (
          <div style={{ color: "#22c55e" }}>
            <strong>+{diff.sections_added}</strong> tilfojet
          </div>
        )}
        {diff.sections_removed > 0 && (
          <div style={{ color: "#ef4444" }}>
            <strong>-{diff.sections_removed}</strong> fjernet
          </div>
        )}
        {diff.sections_modified > 0 && (
          <div style={{ color: "#f59e0b" }}>
            <strong>~{diff.sections_modified}</strong> aendret
          </div>
        )}
      </div>

      {/* Source diff */}
      {diff.source_diff && (
        <SourceDiffSection diff={diff.source_diff} />
      )}

      {/* Section diffs */}
      <h3 style={{ marginTop: "1.5rem", marginBottom: "1rem" }}>Afsnit</h3>
      <div>
        {diff.section_diffs.map((section) => (
          <SectionDiffCard
            key={section.heading}
            section={section}
            expanded={expandedSections.has(section.heading)}
            onToggle={() => toggleSection(section.heading)}
          />
        ))}
      </div>
    </div>
  );
}

interface SourceDiffSectionProps {
  diff: { added: string[]; removed: string[]; unchanged: string[] };
}

function SourceDiffSection({ diff }: SourceDiffSectionProps) {
  const hasChanges = diff.added.length > 0 || diff.removed.length > 0;

  if (!hasChanges) {
    return null;
  }

  return (
    <div
      style={{
        marginBottom: "1.5rem",
        padding: "1rem",
        background: "#fefce8",
        borderRadius: "6px",
        border: "1px solid #fef08a",
      }}
    >
      <h4 style={{ margin: "0 0 0.75rem 0" }}>Kildeaendringer</h4>
      {diff.added.length > 0 && (
        <div style={{ marginBottom: "0.5rem" }}>
          <span style={{ color: "#22c55e", fontWeight: "bold" }}>Tilfojet:</span>{" "}
          {diff.added.join(", ")}
        </div>
      )}
      {diff.removed.length > 0 && (
        <div>
          <span style={{ color: "#ef4444", fontWeight: "bold" }}>Fjernet:</span>{" "}
          {diff.removed.join(", ")}
        </div>
      )}
    </div>
  );
}

interface SectionDiffCardProps {
  section: SectionDiff;
  expanded: boolean;
  onToggle: () => void;
}

function SectionDiffCard({ section, expanded, onToggle }: SectionDiffCardProps) {
  const getChangeColor = () => {
    switch (section.change_type) {
      case "added":
        return { bg: "#f0fdf4", border: "#bbf7d0", badge: "#22c55e", text: "Tilfojet" };
      case "removed":
        return { bg: "#fef2f2", border: "#fecaca", badge: "#ef4444", text: "Fjernet" };
      case "modified":
        return { bg: "#fffbeb", border: "#fde68a", badge: "#f59e0b", text: "Aendret" };
      default:
        return { bg: "#f9fafb", border: "#e5e7eb", badge: "#6b7280", text: "Uaendret" };
    }
  };

  const colors = getChangeColor();

  return (
    <div
      style={{
        background: colors.bg,
        border: `1px solid ${colors.border}`,
        borderRadius: "6px",
        marginBottom: "0.75rem",
        overflow: "hidden",
      }}
    >
      {/* Header */}
      <div
        onClick={section.change_type !== "unchanged" ? onToggle : undefined}
        style={{
          padding: "0.75rem 1rem",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          cursor: section.change_type !== "unchanged" ? "pointer" : "default",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
          <span
            style={{
              fontSize: "0.7rem",
              fontWeight: "600",
              color: "#fff",
              background: colors.badge,
              padding: "0.15rem 0.5rem",
              borderRadius: "9999px",
            }}
          >
            {colors.text}
          </span>
          <strong>{section.heading}</strong>
        </div>
        {section.change_type !== "unchanged" && (
          <span className="muted">{expanded ? "Skjul" : "Vis detaljer"}</span>
        )}
      </div>

      {/* Expanded content */}
      {expanded && section.change_type !== "unchanged" && (
        <div
          style={{
            padding: "1rem",
            borderTop: `1px solid ${colors.border}`,
            background: "rgba(255,255,255,0.5)",
          }}
        >
          {section.change_type === "modified" && section.unified_diff && (
            <DiffView diff={section.unified_diff} />
          )}
          {section.change_type === "added" && section.new_content && (
            <div>
              <div className="muted" style={{ marginBottom: "0.5rem" }}>
                Nyt indhold:
              </div>
              <pre
                style={{
                  background: "#fff",
                  padding: "0.75rem",
                  borderRadius: "4px",
                  overflow: "auto",
                  fontSize: "0.85rem",
                  whiteSpace: "pre-wrap",
                  margin: 0,
                }}
              >
                {section.new_content}
              </pre>
            </div>
          )}
          {section.change_type === "removed" && section.old_content && (
            <div>
              <div className="muted" style={{ marginBottom: "0.5rem" }}>
                Fjernet indhold:
              </div>
              <pre
                style={{
                  background: "#fff",
                  padding: "0.75rem",
                  borderRadius: "4px",
                  overflow: "auto",
                  fontSize: "0.85rem",
                  whiteSpace: "pre-wrap",
                  margin: 0,
                  textDecoration: "line-through",
                  color: "#ef4444",
                }}
              >
                {section.old_content}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

interface DiffViewProps {
  diff: string;
}

function DiffView({ diff }: DiffViewProps) {
  const lines = diff.split("\n");

  return (
    <pre
      style={{
        background: "#fff",
        padding: "0.75rem",
        borderRadius: "4px",
        overflow: "auto",
        fontSize: "0.8rem",
        fontFamily: "monospace",
        margin: 0,
        lineHeight: 1.5,
      }}
    >
      {lines.map((line, i) => {
        let color = "#374151";
        let bg = "transparent";

        if (line.startsWith("+") && !line.startsWith("+++")) {
          color = "#22c55e";
          bg = "#f0fdf4";
        } else if (line.startsWith("-") && !line.startsWith("---")) {
          color = "#ef4444";
          bg = "#fef2f2";
        } else if (line.startsWith("@@")) {
          color = "#8b5cf6";
          bg = "#f5f3ff";
        }

        return (
          <div key={i} style={{ color, background: bg, padding: "0 0.25rem" }}>
            {line || " "}
          </div>
        );
      })}
    </pre>
  );
}
