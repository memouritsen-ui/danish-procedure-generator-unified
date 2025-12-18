/**
 * SSE Hook for real-time pipeline progress updates.
 *
 * Connects to the SSE endpoint and provides:
 * - Current agent being executed
 * - Quality score updates
 * - Cost tracking
 * - Error handling
 */
import { useState, useEffect, useCallback, useRef } from 'react';

// Event types from backend
export type SSEEventType =
  | 'progress'
  | 'sources_found'
  | 'agent_start'
  | 'agent_complete'
  | 'quality_check'
  | 'iteration_start'
  | 'complete'
  | 'error'
  | 'cost_update';

export interface SSEEvent {
  event: SSEEventType;
  data: Record<string, unknown>;
  timestamp: number;
}

export interface SSEState {
  connected: boolean;
  currentAgent: string | null;
  currentIteration: number;
  maxIterations: number;
  qualityScore: number | null;
  totalCostUsd: number;
  totalTokens: number;
  sourcesFound: number;
  isComplete: boolean;
  error: string | null;
  events: SSEEvent[];
}

const initialState: SSEState = {
  connected: false,
  currentAgent: null,
  currentIteration: 0,
  maxIterations: 3,
  qualityScore: null,
  totalCostUsd: 0,
  totalTokens: 0,
  sourcesFound: 0,
  isComplete: false,
  error: null,
  events: [],
};

/**
 * Hook to subscribe to SSE events for a pipeline run.
 *
 * @param runId - The run ID to subscribe to
 * @param enabled - Whether to connect (default: true)
 * @returns SSE state with current progress
 */
export function useSSE(runId: string | null, enabled: boolean = true): SSEState {
  const [state, setState] = useState<SSEState>(initialState);
  const eventSourceRef = useRef<EventSource | null>(null);

  const handleEvent = useCallback((event: SSEEvent) => {
    setState((prev) => {
      const newState = { ...prev, events: [...prev.events, event] };

      switch (event.event) {
        case 'progress':
          // General progress message - no state change needed
          break;

        case 'sources_found':
          newState.sourcesFound = (event.data.count as number) || 0;
          break;

        case 'agent_start':
          newState.currentAgent = event.data.agent as string;
          break;

        case 'agent_complete':
          // Agent completed - could update to show completion
          break;

        case 'iteration_start':
          newState.currentIteration = event.data.iteration as number;
          newState.maxIterations = event.data.max_iterations as number;
          break;

        case 'quality_check':
          newState.qualityScore = event.data.score as number;
          break;

        case 'cost_update':
          newState.totalCostUsd = event.data.total_cost_usd as number;
          newState.totalTokens = event.data.total_tokens as number;
          break;

        case 'complete':
          newState.isComplete = true;
          newState.currentAgent = null;
          newState.qualityScore = event.data.quality_score as number;
          newState.totalCostUsd = event.data.total_cost_usd as number;
          break;

        case 'error':
          newState.error = event.data.error as string;
          newState.isComplete = true;
          break;
      }

      return newState;
    });
  }, []);

  useEffect(() => {
    if (!runId || !enabled) {
      setState(initialState);
      return;
    }

    // Reset state for new run
    setState({ ...initialState, connected: true });

    const eventSource = new EventSource(`/api/runs/${runId}/events`);
    eventSourceRef.current = eventSource;

    eventSource.onmessage = (e) => {
      try {
        const event: SSEEvent = JSON.parse(e.data);
        handleEvent(event);
      } catch (err) {
        console.error('Failed to parse SSE event:', err, e.data);
      }
    };

    eventSource.onerror = (err) => {
      console.error('SSE connection error:', err);
      // EventSource will auto-reconnect, but mark as potentially disconnected
      setState((prev) => ({
        ...prev,
        connected: false,
      }));
    };

    eventSource.onopen = () => {
      setState((prev) => ({
        ...prev,
        connected: true,
      }));
    };

    return () => {
      eventSource.close();
      eventSourceRef.current = null;
    };
  }, [runId, enabled, handleEvent]);

  return state;
}

/**
 * Get agent display name in Danish.
 */
export function getAgentDisplayName(agent: string | null): string {
  if (!agent) return '';

  const names: Record<string, string> = {
    Researcher: 'Kilde-research',
    Writer: 'Skriver procedure',
    Validator: 'Validerer kilder',
    Editor: 'Redigerer tekst',
    Quality: 'Kvalitetskontrol',
  };

  return names[agent] || agent;
}

/**
 * Get agent progress percentage (0-100).
 */
export function getAgentProgress(currentAgent: string | null): number {
  if (!currentAgent) return 0;

  const agentOrder = ['Researcher', 'Writer', 'Validator', 'Editor', 'Quality'];
  const index = agentOrder.indexOf(currentAgent);

  if (index === -1) return 50;

  // Each agent is 20% of the progress
  return (index + 1) * 20;
}
