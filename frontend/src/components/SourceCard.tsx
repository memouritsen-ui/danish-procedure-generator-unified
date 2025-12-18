/**
 * Source Card Component
 *
 * Displays source metadata with composite trust score and reasoning breakdown.
 * Color-coded by score: green (80+), yellow (60-79), red (<60).
 */
import { SourceRecord, SourceScore } from "../api";

interface SourceCardProps {
  source: SourceRecord;
  score?: SourceScore;
  expanded?: boolean;
  onToggle?: () => void;
}

function getScoreColor(score: number | undefined): string {
  if (score === undefined) return '#888';
  if (score >= 80) return '#22c55e'; // green
  if (score >= 60) return '#fbbf24'; // yellow
  return '#f87171'; // red
}

function getScoreBadge(score: number | undefined): string {
  if (score === undefined) return '-';
  if (score >= 80) return 'Høj tillid';
  if (score >= 60) return 'Moderat tillid';
  return 'Lav tillid';
}

export function SourceCard({
  source,
  score,
  expanded = false,
  onToggle,
}: SourceCardProps) {
  const scoreColor = getScoreColor(score?.composite_score);
  const trustBadge = getScoreBadge(score?.composite_score);

  // Get year from score or source
  const year = score?.recency_year ?? source.year;

  return (
    <div className="source-card">
      <div
        className="source-header"
        onClick={onToggle}
        style={{ cursor: onToggle ? 'pointer' : 'default' }}
      >
        <div className="source-info">
          <div className="source-title">
            <strong>{source.source_id}</strong>
            <span className="source-kind">({source.kind})</span>
          </div>
          <div className="source-meta">
            {source.title ?? source.url ?? (source.pmid ? `PMID: ${source.pmid}` : '-')}
          </div>
        </div>

        {score && (
          <div className="trust-score-container">
            <div
              className="trust-score"
              style={{ color: scoreColor, borderColor: scoreColor }}
            >
              {score.composite_score.toFixed(0)}
            </div>
            <div className="trust-badge" style={{ color: scoreColor }}>
              {trustBadge}
            </div>
          </div>
        )}
      </div>

      {/* Quick stats row */}
      <div className="source-stats">
        {year && <span className="stat-item">År: {year}</span>}
        {score && (
          <>
            <span className="stat-item">Evidens: {score.evidence_level}</span>
            <span className="stat-item">
              Aktualitet: {(score.recency_score * 100).toFixed(0)}%
            </span>
            <span className="stat-item">
              Kvalitet: {(score.quality_score * 100).toFixed(0)}%
            </span>
          </>
        )}
        {source.doi && <span className="stat-item">DOI: {source.doi}</span>}
        {source.pmid && <span className="stat-item">PMID: {source.pmid}</span>}
      </div>

      {/* Expanded reasoning */}
      {expanded && score?.reasoning && score.reasoning.length > 0 && (
        <div className="score-breakdown">
          <strong>Scoreberegning:</strong>
          <ul>
            {score.reasoning.map((reason, i) => (
              <li key={i}>{reason}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

// CSS styles
const styles = `
.source-card {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 1rem;
  margin-bottom: 0.75rem;
  transition: box-shadow 0.2s;
}

.source-card:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.source-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
}

.source-info {
  flex: 1;
  min-width: 0;
}

.source-title {
  font-size: 0.9rem;
  margin-bottom: 0.25rem;
}

.source-kind {
  color: #6b7280;
  font-size: 0.8rem;
  margin-left: 0.5rem;
}

.source-meta {
  color: #6b7280;
  font-size: 0.85rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.trust-score-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 60px;
}

.trust-score {
  font-size: 1.25rem;
  font-weight: bold;
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 2px solid;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.9);
}

.trust-badge {
  font-size: 0.7rem;
  font-weight: 500;
  margin-top: 0.25rem;
  text-align: center;
}

.source-stats {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem 1rem;
  margin-top: 0.5rem;
  padding-top: 0.5rem;
  border-top: 1px solid #f3f4f6;
}

.stat-item {
  font-size: 0.75rem;
  color: #6b7280;
}

.score-breakdown {
  margin-top: 0.75rem;
  padding: 0.75rem;
  background: #f9fafb;
  border-radius: 4px;
  font-size: 0.8rem;
}

.score-breakdown strong {
  display: block;
  margin-bottom: 0.5rem;
  color: #374151;
}

.score-breakdown ul {
  margin: 0;
  padding-left: 1.25rem;
}

.score-breakdown li {
  color: #6b7280;
  line-height: 1.6;
}
`;

// Inject styles
if (typeof document !== 'undefined') {
  const styleElement = document.createElement('style');
  styleElement.textContent = styles;
  document.head.appendChild(styleElement);
}

export type { SourceCardProps };
