export type WriteRequest = { procedure: string; context?: string; template_id?: string };
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

// --- Versioning API ---

export type ProceduresResponse = {
  procedures: string[];
  count: number;
};

export type VersionInfo = {
  run_id: string;
  version_number: number;
  created_at_utc: string;
  parent_run_id: string | null;
  version_note: string | null;
  quality_score: number | null;
  status: string;
};

export type ProcedureVersionsResponse = {
  procedure: string;
  count: number;
  versions: VersionInfo[];
};

export type VersionChainResponse = {
  run_id: string;
  chain_length: number;
  chain: VersionInfo[];
};

export type SectionDiff = {
  heading: string;
  change_type: "added" | "removed" | "modified" | "unchanged";
  old_content: string | null;
  new_content: string | null;
  unified_diff: string | null;
  similarity: number;
};

export type SourceDiff = {
  added: string[];
  removed: string[];
  unchanged: string[];
};

export type VersionDiff = {
  old_run_id: string;
  new_run_id: string;
  old_version: number;
  new_version: number;
  procedure: string;
  has_changes: boolean;
  summary: string;
  sections_added: number;
  sections_removed: number;
  sections_modified: number;
  section_diffs: SectionDiff[];
  source_diff: SourceDiff | null;
};

export async function apiProcedures(): Promise<ProceduresResponse> {
  const resp = await fetch("/api/procedures");
  if (!resp.ok) throw new Error(await resp.text());
  return (await resp.json()) as ProceduresResponse;
}

export async function apiProcedureVersions(procedure: string): Promise<ProcedureVersionsResponse> {
  const resp = await fetch(`/api/procedures/${encodeURIComponent(procedure)}/versions`);
  if (!resp.ok) throw new Error(await resp.text());
  return (await resp.json()) as ProcedureVersionsResponse;
}

export async function apiVersionChain(runId: string): Promise<VersionChainResponse> {
  const resp = await fetch(`/api/runs/${encodeURIComponent(runId)}/version-chain`);
  if (!resp.ok) throw new Error(await resp.text());
  return (await resp.json()) as VersionChainResponse;
}

export async function apiDiff(runId: string, otherRunId: string): Promise<VersionDiff> {
  const resp = await fetch(`/api/runs/${encodeURIComponent(runId)}/diff/${encodeURIComponent(otherRunId)}`);
  if (!resp.ok) throw new Error(await resp.text());
  return (await resp.json()) as VersionDiff;
}

// --- Template API ---

export type SectionConfig = {
  heading: string;
  format: "bullets" | "numbered" | "paragraphs";
  bundle: "action" | "explanation" | "safety";
};

export type TemplateConfig = {
  title_prefix: string;
  sections: SectionConfig[];
};

export type TemplateSummary = {
  template_id: string;
  name: string;
  description: string | null;
  is_default: boolean;
  is_system: boolean;
  section_count: number;
};

export type TemplateDetail = {
  template_id: string;
  name: string;
  description: string | null;
  is_default: boolean;
  is_system: boolean;
  created_at_utc: string;
  updated_at_utc: string;
  config: TemplateConfig;
};

export type TemplatesResponse = {
  templates: TemplateSummary[];
};

export async function apiListTemplates(): Promise<TemplatesResponse> {
  const resp = await fetch("/api/templates");
  if (!resp.ok) throw new Error(await resp.text());
  return (await resp.json()) as TemplatesResponse;
}

export async function apiGetTemplate(templateId: string): Promise<TemplateDetail> {
  const resp = await fetch(`/api/templates/${encodeURIComponent(templateId)}`);
  if (!resp.ok) throw new Error(await resp.text());
  return (await resp.json()) as TemplateDetail;
}

export async function apiCreateTemplate(
  name: string,
  config: TemplateConfig,
  description?: string
): Promise<string> {
  const resp = await fetch("/api/templates", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, description, config }),
  });
  if (!resp.ok) throw new Error(await resp.text());
  const json = (await resp.json()) as { template_id: string };
  return json.template_id;
}

export async function apiUpdateTemplate(
  templateId: string,
  updates: { name?: string; description?: string; config?: TemplateConfig }
): Promise<void> {
  const resp = await fetch(`/api/templates/${encodeURIComponent(templateId)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(updates),
  });
  if (!resp.ok) throw new Error(await resp.text());
}

export async function apiDeleteTemplate(templateId: string): Promise<void> {
  const resp = await fetch(`/api/templates/${encodeURIComponent(templateId)}`, {
    method: "DELETE",
  });
  if (!resp.ok) throw new Error(await resp.text());
}

export async function apiSetDefaultTemplate(templateId: string): Promise<void> {
  const resp = await fetch(`/api/templates/${encodeURIComponent(templateId)}/set-default`, {
    method: "POST",
  });
  if (!resp.ok) throw new Error(await resp.text());
}

// --- Protocol API ---

export type Protocol = {
  protocol_id: string;
  name: string;
  description: string | null;
  status: string;
  version: string | null;
  approved_by: string | null;
  created_at_utc: string;
};

export type ProtocolsResponse = {
  protocols: Protocol[];
};

export type ProtocolSearchResult = {
  protocol_id: string;
  name: string;
  similarity: number;
};

export type ProtocolSearchResponse = {
  query: string;
  results: ProtocolSearchResult[];
};

export async function apiListProtocols(status: string = "active"): Promise<ProtocolsResponse> {
  const resp = await fetch(`/api/protocols?status=${encodeURIComponent(status)}`);
  if (!resp.ok) throw new Error(await resp.text());
  return (await resp.json()) as ProtocolsResponse;
}

export async function apiGetProtocol(protocolId: string): Promise<Protocol & { has_text: boolean }> {
  const resp = await fetch(`/api/protocols/${encodeURIComponent(protocolId)}`);
  if (!resp.ok) throw new Error(await resp.text());
  return (await resp.json()) as Protocol & { has_text: boolean };
}

export async function apiUploadProtocol(
  file: File,
  name: string,
  description?: string,
  version?: string,
  approvedBy?: string
): Promise<string> {
  const form = new FormData();
  form.append("file", file);
  form.append("name", name);
  if (description) form.append("description", description);
  if (version) form.append("version", version);
  if (approvedBy) form.append("approved_by", approvedBy);

  const resp = await fetch("/api/protocols/upload", { method: "POST", body: form });
  if (!resp.ok) throw new Error(await resp.text());
  const json = (await resp.json()) as { protocol_id: string };
  return json.protocol_id;
}

export async function apiUpdateProtocol(
  protocolId: string,
  updates: {
    name?: string;
    description?: string;
    status?: string;
    version?: string;
    approved_by?: string;
  }
): Promise<void> {
  const resp = await fetch(`/api/protocols/${encodeURIComponent(protocolId)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(updates),
  });
  if (!resp.ok) throw new Error(await resp.text());
}

export async function apiDeleteProtocol(protocolId: string): Promise<void> {
  const resp = await fetch(`/api/protocols/${encodeURIComponent(protocolId)}`, {
    method: "DELETE",
  });
  if (!resp.ok) throw new Error(await resp.text());
}

export async function apiSearchProtocols(query: string, threshold: number = 0.5): Promise<ProtocolSearchResponse> {
  const resp = await fetch(`/api/protocols/search?q=${encodeURIComponent(query)}&threshold=${threshold}`);
  if (!resp.ok) throw new Error(await resp.text());
  return (await resp.json()) as ProtocolSearchResponse;
}

// --- Validation API ---

export type Conflict = {
  section: string;
  type: string;
  severity: "critical" | "warning" | "info";
  explanation: string;
  generated_text: string;
  approved_text: string;
};

export type ValidationResult = {
  validation_id: string;
  protocol_id: string;
  protocol_name: string;
  name_similarity: number;
  content_similarity: number;
  compatibility_score: number | null;  // 0-100 from LLM
  summary: string | null;  // LLM assessment summary
  conflict_count: number;
  conflicts: Conflict[];
  validation_cost_usd: number | null;
};

export type ValidationsResponse = {
  run_id: string;
  validations: ValidationResult[];
  total_validation_cost_usd?: number;
};

export async function apiValidateRun(runId: string, protocolId?: string): Promise<ValidationsResponse> {
  const url = protocolId
    ? `/api/runs/${encodeURIComponent(runId)}/validate?protocol_id=${encodeURIComponent(protocolId)}`
    : `/api/runs/${encodeURIComponent(runId)}/validate`;

  const resp = await fetch(url, { method: "POST" });
  if (!resp.ok) throw new Error(await resp.text());
  return (await resp.json()) as ValidationsResponse;
}

export async function apiGetValidations(runId: string): Promise<ValidationsResponse> {
  const resp = await fetch(`/api/runs/${encodeURIComponent(runId)}/validations`);
  if (!resp.ok) throw new Error(await resp.text());
  return (await resp.json()) as ValidationsResponse;
}
