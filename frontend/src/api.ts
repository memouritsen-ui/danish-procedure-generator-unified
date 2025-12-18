export type WriteRequest = { procedure: string; context?: string };
export type WriteResponse = { run_id: string };

export type RunSummary = {
  run_id: string;
  created_at_utc: string;
  updated_at_utc: string;
  procedure: string;
  status: string;
  quality_score?: number | null;
  iterations_used?: number | null;
  total_cost_usd?: number | null;
};

export type RunDetail = RunSummary & {
  context?: string | null;
  error?: string | null;
  procedure_md?: string | null;
  source_count?: number | null;
  warnings?: string[] | null;
  total_input_tokens?: number | null;
  total_output_tokens?: number | null;
};

export type SourceRecord = {
  source_id: string;
  fetched_at_utc: string;
  kind: string;
  title?: string | null;
  year?: number | null;
  url?: string | null;
  doi?: string | null;
  pmid?: string | null;
  raw_path: string;
  normalized_path: string;
  raw_sha256: string;
  normalized_sha256: string;
  extraction_notes?: string | null;
  terms_licence_note?: string | null;
  extra?: Record<string, unknown>;
};

export type SourcesResponse = { run_id: string; sources: SourceRecord[] };

export type SourceScore = {
  source_id: string;
  evidence_level: string;
  evidence_priority: number;
  recency_score: number;
  recency_year: number | null;
  quality_score: number;
  composite_score: number;
  reasoning: string[];
};

export type SourceScoresResponse = {
  run_id: string;
  count: number;
  scores: SourceScore[];
};

export type ApiKeyInfo = { present: boolean; masked?: string | null };
export type ApiKeyStatus = { present: boolean; ok: boolean; message: string };
export type AppStatus = {
  version: string;
  dummy_mode: boolean;
  use_llm: boolean;
  llm_provider: string;
  llm_model: string;
  openai_embeddings_model: string;
  openai_base_url: string;
  openai_key_present: boolean;
  openai_key_source: string;
  anthropic_key_present: boolean;
  anthropic_key_source: string;
  ollama_base_url: string;
  ncbi_api_key_present: boolean;
  ncbi_api_key_source: string;
  ncbi_tool: string;
  ncbi_email?: string | null;
};

export type EvidenceMatch = {
  source_id: string;
  supported: boolean;
  bm25: number;
  overlap: number;
  snippet: { source_id: string | null; location: unknown; excerpt: string | null };
};

export type EvidenceSentence = {
  line_no: number;
  text: string;
  clean_text: string;
  citations: string[];
  supported: boolean;
  matches: EvidenceMatch[];
};

export type EvidenceReport = {
  version: number;
  sentence_count: number;
  supported_count: number;
  unsupported_count: number;
  sentences: EvidenceSentence[];
};

export async function apiWrite(req: WriteRequest): Promise<string> {
  const resp = await fetch("/api/write", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!resp.ok) throw new Error(await resp.text());
  const json = (await resp.json()) as WriteResponse;
  return json.run_id;
}

export async function apiRuns(): Promise<RunSummary[]> {
  const resp = await fetch("/api/runs");
  if (!resp.ok) throw new Error(await resp.text());
  return (await resp.json()) as RunSummary[];
}

export async function apiRun(runId: string): Promise<RunDetail> {
  const resp = await fetch(`/api/runs/${encodeURIComponent(runId)}`);
  if (!resp.ok) throw new Error(await resp.text());
  return (await resp.json()) as RunDetail;
}

export async function apiSources(runId: string): Promise<SourcesResponse> {
  const resp = await fetch(`/api/runs/${encodeURIComponent(runId)}/sources`);
  if (!resp.ok) throw new Error(await resp.text());
  return (await resp.json()) as SourcesResponse;
}

export async function apiSourceScores(runId: string): Promise<SourceScoresResponse> {
  const resp = await fetch(`/api/runs/${encodeURIComponent(runId)}/sources/scores`);
  if (!resp.ok) throw new Error(await resp.text());
  return (await resp.json()) as SourceScoresResponse;
}

export async function apiGetConfig(name: "author_guide" | "source_allowlist" | "docx_template"): Promise<string> {
  const resp = await fetch(`/api/config/${name}`);
  if (!resp.ok) throw new Error(await resp.text());
  const json = (await resp.json()) as { text: string };
  return json.text;
}

export async function apiSetConfig(name: "author_guide" | "source_allowlist" | "docx_template", text: string): Promise<void> {
  const resp = await fetch(`/api/config/${name}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  if (!resp.ok) throw new Error(await resp.text());
}

export async function apiGetOpenAiKey(): Promise<ApiKeyInfo> {
  const resp = await fetch("/api/keys/openai");
  if (!resp.ok) throw new Error(await resp.text());
  return (await resp.json()) as ApiKeyInfo;
}

export async function apiSetOpenAiKey(api_key: string): Promise<ApiKeyInfo> {
  const resp = await fetch("/api/keys/openai", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ api_key }),
  });
  if (!resp.ok) throw new Error(await resp.text());
  return (await resp.json()) as ApiKeyInfo;
}

export async function apiDeleteOpenAiKey(): Promise<ApiKeyInfo> {
  const resp = await fetch("/api/keys/openai", { method: "DELETE" });
  if (!resp.ok) throw new Error(await resp.text());
  return (await resp.json()) as ApiKeyInfo;
}

export async function apiOpenAiStatus(): Promise<ApiKeyStatus> {
  const resp = await fetch("/api/keys/openai/status");
  if (!resp.ok) throw new Error(await resp.text());
  return (await resp.json()) as ApiKeyStatus;
}

export async function apiGetNcbiKey(): Promise<ApiKeyInfo> {
  const resp = await fetch("/api/keys/ncbi");
  if (!resp.ok) throw new Error(await resp.text());
  return (await resp.json()) as ApiKeyInfo;
}

export async function apiSetNcbiKey(api_key: string): Promise<ApiKeyInfo> {
  const resp = await fetch("/api/keys/ncbi", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ api_key }),
  });
  if (!resp.ok) throw new Error(await resp.text());
  return (await resp.json()) as ApiKeyInfo;
}

export async function apiDeleteNcbiKey(): Promise<ApiKeyInfo> {
  const resp = await fetch("/api/keys/ncbi", { method: "DELETE" });
  if (!resp.ok) throw new Error(await resp.text());
  return (await resp.json()) as ApiKeyInfo;
}

export async function apiNcbiStatus(): Promise<ApiKeyStatus> {
  const resp = await fetch("/api/keys/ncbi/status");
  if (!resp.ok) throw new Error(await resp.text());
  return (await resp.json()) as ApiKeyStatus;
}

export async function apiGetAnthropicKey(): Promise<ApiKeyInfo> {
  const resp = await fetch("/api/keys/anthropic");
  if (!resp.ok) throw new Error(await resp.text());
  return (await resp.json()) as ApiKeyInfo;
}

export async function apiSetAnthropicKey(api_key: string): Promise<ApiKeyInfo> {
  const resp = await fetch("/api/keys/anthropic", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ api_key }),
  });
  if (!resp.ok) throw new Error(await resp.text());
  return (await resp.json()) as ApiKeyInfo;
}

export async function apiDeleteAnthropicKey(): Promise<ApiKeyInfo> {
  const resp = await fetch("/api/keys/anthropic", { method: "DELETE" });
  if (!resp.ok) throw new Error(await resp.text());
  return (await resp.json()) as ApiKeyInfo;
}

export async function apiAnthropicStatus(): Promise<ApiKeyStatus> {
  const resp = await fetch("/api/keys/anthropic/status");
  if (!resp.ok) throw new Error(await resp.text());
  return (await resp.json()) as ApiKeyStatus;
}

export async function apiStatus(): Promise<AppStatus> {
  const resp = await fetch("/api/status");
  if (!resp.ok) throw new Error(await resp.text());
  return (await resp.json()) as AppStatus;
}

export async function apiEvidence(runId: string): Promise<EvidenceReport> {
  const resp = await fetch(`/api/runs/${encodeURIComponent(runId)}/evidence`);
  if (!resp.ok) throw new Error(await resp.text());
  return (await resp.json()) as EvidenceReport;
}

export async function apiIngestUrl(url: string): Promise<string> {
  const resp = await fetch("/api/ingest/url", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  });
  if (!resp.ok) throw new Error(await resp.text());
  const json = (await resp.json()) as { source_id: string };
  return json.source_id;
}

export async function apiIngestPdf(file: File): Promise<string> {
  const form = new FormData();
  form.append("file", file);
  const resp = await fetch("/api/ingest/pdf", { method: "POST", body: form });
  if (!resp.ok) throw new Error(await resp.text());
  const json = (await resp.json()) as { source_id: string };
  return json.source_id;
}

export async function apiIngestDocx(file: File): Promise<string> {
  const form = new FormData();
  form.append("file", file);
  const resp = await fetch("/api/ingest/docx", { method: "POST", body: form });
  if (!resp.ok) throw new Error(await resp.text());
  const json = (await resp.json()) as { source_id: string };
  return json.source_id;
}

// Library stats and search
export type LibraryStats = {
  available: boolean;
  document_count: number;
  source_stats: Record<string, number>;
  library_path: string;
};

export type LibrarySearchResult = {
  doc_id: string;
  source_id: string;
  source_name: string;
  title: string;
  url: string;
  publish_year?: string | null;
  category?: string | null;
  relevance_score: number;
};

export type LibrarySearchResponse = {
  query: string;
  count: number;
  results: LibrarySearchResult[];
};

export async function apiLibraryStats(): Promise<LibraryStats> {
  const resp = await fetch("/api/library/stats");
  if (!resp.ok) throw new Error(await resp.text());
  return (await resp.json()) as LibraryStats;
}

export async function apiLibrarySearch(query: string, limit: number = 20): Promise<LibrarySearchResponse> {
  const resp = await fetch(`/api/library/search?q=${encodeURIComponent(query)}&limit=${limit}`);
  if (!resp.ok) throw new Error(await resp.text());
  return (await resp.json()) as LibrarySearchResponse;
}
