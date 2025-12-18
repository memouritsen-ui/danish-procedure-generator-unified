/**
 * Progress indicator for pipeline execution with SSE updates.
 *
 * Shows:
 * - Current agent being executed
 * - Progress bar
 * - Quality score
 * - Cost tracking
 */
import { useSSE, getAgentDisplayName, getAgentProgress } from '../hooks/useSSE';

interface ProgressIndicatorProps {
  runId: string | null;
  enabled?: boolean;
}

export function ProgressIndicator({ runId, enabled = true }: ProgressIndicatorProps) {
  const state = useSSE(runId, enabled);

  if (!runId || (!enabled && !state.isComplete)) {
    return null;
  }

  const progress = state.isComplete ? 100 : getAgentProgress(state.currentAgent);

  return (
    <div className="progress-indicator">
      {/* Progress bar */}
      <div className="progress-bar-container">
        <div
          className="progress-bar"
          style={{ width: `${progress}%` }}
        />
      </div>

      {/* Status text */}
      <div className="progress-status">
        {state.error ? (
          <span className="status-error">
            Fejl: {state.error}
          </span>
        ) : state.isComplete ? (
          <span className="status-complete">
            Procedure genereret (kvalitet: {state.qualityScore}/10)
          </span>
        ) : state.currentAgent ? (
          <span className="status-running">
            {getAgentDisplayName(state.currentAgent)}
            {state.currentIteration > 0 && ` (iteration ${state.currentIteration}/${state.maxIterations})`}
          </span>
        ) : (
          <span className="status-starting">
            Starter...
          </span>
        )}
      </div>

      {/* Cost and sources info */}
      <div className="progress-info">
        {state.sourcesFound > 0 && (
          <span className="info-item">
            {state.sourcesFound} kilder
          </span>
        )}
        {state.totalCostUsd > 0 && (
          <span className="info-item">
            ${state.totalCostUsd.toFixed(4)}
          </span>
        )}
        {state.totalTokens > 0 && (
          <span className="info-item">
            {state.totalTokens.toLocaleString()} tokens
          </span>
        )}
      </div>

      {/* Agent pipeline visualization */}
      {!state.isComplete && (
        <div className="agent-pipeline">
          {['Researcher', 'Writer', 'Validator', 'Editor', 'Quality'].map((agent) => (
            <div
              key={agent}
              className={`agent-step ${
                state.currentAgent === agent
                  ? 'active'
                  : getAgentProgress(state.currentAgent) > getAgentProgress(agent)
                  ? 'complete'
                  : 'pending'
              }`}
            >
              {getAgentDisplayName(agent)}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// CSS styles (can be moved to separate CSS file)
const styles = `
.progress-indicator {
  padding: 1rem;
  background: #f8f9fa;
  border-radius: 8px;
  margin: 1rem 0;
}

.progress-bar-container {
  height: 8px;
  background: #e9ecef;
  border-radius: 4px;
  overflow: hidden;
}

.progress-bar {
  height: 100%;
  background: #0d6efd;
  transition: width 0.3s ease;
}

.progress-status {
  margin-top: 0.5rem;
  font-weight: 500;
}

.status-error {
  color: #dc3545;
}

.status-complete {
  color: #198754;
}

.status-running {
  color: #0d6efd;
}

.status-starting {
  color: #6c757d;
}

.progress-info {
  margin-top: 0.5rem;
  font-size: 0.875rem;
  color: #6c757d;
  display: flex;
  gap: 1rem;
}

.agent-pipeline {
  margin-top: 1rem;
  display: flex;
  gap: 0.5rem;
}

.agent-step {
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  font-size: 0.75rem;
}

.agent-step.active {
  background: #0d6efd;
  color: white;
}

.agent-step.complete {
  background: #198754;
  color: white;
}

.agent-step.pending {
  background: #e9ecef;
  color: #6c757d;
}
`;

// Inject styles
if (typeof document !== 'undefined') {
  const styleElement = document.createElement('style');
  styleElement.textContent = styles;
  document.head.appendChild(styleElement);
}
