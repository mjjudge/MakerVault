/**
 * MakerVault API client.
 *
 * All requests go through the /api prefix, which nginx proxies to the
 * FastAPI backend.  In development, Vite proxies /api → http://api:8000.
 */

import axios from 'axios'

export const apiClient = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
  timeout: 30_000,
})

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface PagedResponse<T> {
  items: T[]
  total: number
}

export interface Category {
  id: string
  name: string
  parent_category_id: string | null
  description: string | null
  sort_order: number | null
  created_at: string
  updated_at: string
}

export interface Location {
  id: string
  name: string
  description: string | null
  parent_location_id: string | null
  created_at: string
  updated_at: string
}

export interface Container {
  id: string
  name: string
  description: string | null
  label_code: string | null
  location_id: string | null
  parent_container_id: string | null
  created_at: string
  updated_at: string
}

export interface Part {
  id: string
  part_code: string
  name: string
  short_description: string | null
  long_description: string | null
  category_id: string | null
  part_kind: string | null
  manufacturer: string | null
  manufacturer_part_number: string | null
  default_unit: string
  package_type: string | null
  spec_summary: string | null
  capabilities_json: Record<string, unknown> | null
  tags: string[] | null
  aliases: string[] | null
  is_consumable: boolean
  is_serialised: boolean
  is_hazardous: boolean
  is_active: boolean
  status: string
  identification_confidence: number | null
  needs_review: boolean
  provenance: string | null
  notes: string | null
  created_at: string
  updated_at: string
  // Taxonomy
  tax_category: string | null
  subcategory: string | null
  family: string | null
  // Electrical / interface
  form_factor: string | null
  interface: string[] | null
  voltage: string | null
  logic_level: string | null
  // Functional
  pins: string[] | null
  capabilities: string[] | null
  use_cases: string[] | null
  key_specs: Record<string, unknown> | null
  // Flags
  protection_features: string[] | null
  special_flags: string[] | null
}

export interface PartAlias {
  id: string
  part_id: string
  alias: string
  notes: string | null
  created_at: string
  updated_at: string
}

export interface Document {
  id: string
  title: string
  document_type: string
  source_type: string
  source_url: string | null
  local_path: string | null
  mime_type: string | null
  checksum: string | null
  file_size_bytes: number | null
  text_extracted: string | null
  summary: string | null
  version_label: string | null
  notes: string | null
  created_at: string
  updated_at: string
}

export interface PartDocumentLink {
  id: string
  part_id: string
  document_id: string
  relationship_type: string
  is_primary: boolean
  notes: string | null
  document: Document
  created_at: string
  updated_at: string
}

export interface StockItemDocumentLink {
  id: string
  stock_item_id: string
  document_id: string
  notes: string | null
  document: Document
  created_at: string
  updated_at: string
}

export interface Project {
  id: string
  name: string
  description: string | null
  status: string
  notes: string | null
  created_at: string
  updated_at: string
}

export interface ProjectPart {
  id: string
  project_id: string
  part_id: string
  quantity_required: number
  unit: string | null
  notes: string | null
  part: Part
  created_at: string
  updated_at: string
}

export interface BOMEntryAvailability {
  project_part_id: string
  part_id: string
  part_code: string
  part_name: string
  quantity_required: number
  total_in_stock: number
  is_available: boolean
}

export interface BOMAvailabilityResponse {
  project_id: string
  entries: BOMEntryAvailability[]
  all_available: boolean
}

export interface AIProviderConfig {
  id: string
  name: string
  provider_type: 'openai' | 'anthropic' | 'ollama' | 'openai_compatible'
  base_url: string | null
  model: string
  api_key_env_var: string | null
  is_enabled: boolean
  is_default: boolean
  notes: string | null
  created_at: string
  updated_at: string
}

export interface HealthCheckResponse {
  provider_id: string
  provider_name: string
  healthy: boolean
  detail: string | null
}


export interface StockItem {
  id: string
  part_id: string
  location_id: string | null
  container_id: string | null
  location_name: string | null
  container_name: string | null
  quantity: number
  unit: string | null
  status: string
  condition: string | null
  serial_number: string | null
  batch_code: string | null
  purchase_date: string | null
  purchase_price: number | null
  purchase_currency: string | null
  supplier: string | null
  notes: string | null
  is_reserved: boolean
  last_seen_at: string | null
  created_at: string
  updated_at: string
}

// ---------------------------------------------------------------------------
// API functions
// ---------------------------------------------------------------------------

export const partsApi = {
  list: (params?: { q?: string; skip?: number; limit?: number; status?: string }) =>
    apiClient.get<PagedResponse<Part>>('/parts', { params }).then(r => r.data),
  get: (id: string) => apiClient.get<Part>(`/parts/${id}`).then(r => r.data),
  create: (data: Partial<Part>) => apiClient.post<Part>('/parts', data).then(r => r.data),
  update: (id: string, data: Partial<Part>) =>
    apiClient.patch<Part>(`/parts/${id}`, data).then(r => r.data),
  delete: (id: string) => apiClient.delete(`/parts/${id}`),
  duplicates: () =>
    apiClient.get<Array<{ reason: string; parts: Partial<Part>[] }>>('/parts/duplicates').then(r => r.data),
  // Aliases
  listAliases: (partId: string) =>
    apiClient.get<PartAlias[]>(`/parts/${partId}/aliases`).then(r => r.data),
  addAlias: (partId: string, data: { alias: string; notes?: string }) =>
    apiClient.post<PartAlias>(`/parts/${partId}/aliases`, data).then(r => r.data),
  removeAlias: (partId: string, aliasId: string) =>
    apiClient.delete(`/parts/${partId}/aliases/${aliasId}`),
}

export const stockApi = {
  list: (params?: { part_id?: string; location_id?: string; container_id?: string; skip?: number; limit?: number }) =>
    apiClient.get<PagedResponse<StockItem>>('/stock', { params }).then(r => r.data),
  get: (id: string) => apiClient.get<StockItem>(`/stock/${id}`).then(r => r.data),
  create: (data: Partial<StockItem>) => apiClient.post<StockItem>('/stock', data).then(r => r.data),
  update: (id: string, data: Partial<StockItem>) =>
    apiClient.patch<StockItem>(`/stock/${id}`, data).then(r => r.data),
  delete: (id: string) => apiClient.delete(`/stock/${id}`),
  bulkMove: (body: { stock_item_ids: string[]; location_id?: string | null; container_id?: string | null }) =>
    apiClient.post<{ moved: number; not_found: string[] }>('/stock/bulk-move', body).then(r => r.data),
}

export const locationsApi = {
  list: (params?: { skip?: number; limit?: number }) =>
    apiClient.get<PagedResponse<Location>>('/locations', { params }).then(r => r.data),
  get: (id: string) => apiClient.get<Location>(`/locations/${id}`).then(r => r.data),
  create: (data: Partial<Location>) => apiClient.post<Location>('/locations', data).then(r => r.data),
  update: (id: string, data: Partial<Location>) =>
    apiClient.patch<Location>(`/locations/${id}`, data).then(r => r.data),
  delete: (id: string) => apiClient.delete(`/locations/${id}`),
}

export const containersApi = {
  list: (params?: { location_id?: string; parent_container_id?: string; skip?: number; limit?: number }) =>
    apiClient.get<PagedResponse<Container>>('/containers', { params }).then(r => r.data),
  get: (id: string) => apiClient.get<Container>(`/containers/${id}`).then(r => r.data),
  create: (data: Partial<Container>) => apiClient.post<Container>('/containers', data).then(r => r.data),
  update: (id: string, data: Partial<Container>) =>
    apiClient.patch<Container>(`/containers/${id}`, data).then(r => r.data),
  delete: (id: string) => apiClient.delete(`/containers/${id}`),
}

export const categoriesApi = {
  list: (params?: { skip?: number; limit?: number }) =>
    apiClient.get<PagedResponse<Category>>('/categories', { params }).then(r => r.data),
  get: (id: string) => apiClient.get<Category>(`/categories/${id}`).then(r => r.data),
  create: (data: Partial<Category>) => apiClient.post<Category>('/categories', data).then(r => r.data),
  update: (id: string, data: Partial<Category>) =>
    apiClient.patch<Category>(`/categories/${id}`, data).then(r => r.data),
  delete: (id: string) => apiClient.delete(`/categories/${id}`),
}

// Note: documents API uses /api/v1 prefix (versioned endpoint introduced in Epic 6)
const docsClient = axios.create({
  baseURL: '/api/v1',
  timeout: 30_000,
})

export const documentsApi = {
  list: (params?: { q?: string; document_type?: string; skip?: number; limit?: number }) =>
    docsClient.get<PagedResponse<Document>>('/documents', { params }).then(r => r.data),
  get: (id: string) => docsClient.get<Document>(`/documents/${id}`).then(r => r.data),
  upload: (formData: FormData) =>
    docsClient.post<Document>('/documents/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then(r => r.data),
  update: (id: string, data: Partial<Document>) =>
    docsClient.patch<Document>(`/documents/${id}`, data).then(r => r.data),
  delete: (id: string) => docsClient.delete(`/documents/${id}`),
  // Part links
  listForPart: (partId: string) =>
    docsClient.get<PartDocumentLink[]>(`/parts/${partId}/documents`).then(r => r.data),
  linkToPart: (partId: string, data: { document_id: string; relationship_type?: string; is_primary?: boolean; notes?: string }) =>
    docsClient.post<PartDocumentLink>(`/parts/${partId}/documents`, data).then(r => r.data),
  unlinkFromPart: (partId: string, linkId: string) =>
    docsClient.delete(`/parts/${partId}/documents/${linkId}`),
  // Stock item links
  listForStockItem: (stockItemId: string) =>
    docsClient.get<StockItemDocumentLink[]>(`/stock/${stockItemId}/documents`).then(r => r.data),
  linkToStockItem: (stockItemId: string, data: { document_id: string; notes?: string }) =>
    docsClient.post<StockItemDocumentLink>(`/stock/${stockItemId}/documents`, data).then(r => r.data),
  unlinkFromStockItem: (stockItemId: string, linkId: string) =>
    docsClient.delete(`/stock/${stockItemId}/documents/${linkId}`),
  // Project links
  listForProject: (projectId: string) =>
    docsClient.get<any[]>(`/projects/${projectId}/documents`).then(r => r.data),
  linkToProject: (projectId: string, data: { document_id: string; relationship_type?: string; notes?: string }) =>
    docsClient.post<any>(`/projects/${projectId}/documents`, data).then(r => r.data),
  unlinkFromProject: (projectId: string, linkId: string) =>
    docsClient.delete(`/projects/${projectId}/documents/${linkId}`),
}

export const projectsApi = {
  list: (params?: { q?: string; status?: string; skip?: number; limit?: number }) =>
    apiClient.get<PagedResponse<Project>>('/projects', { params }).then(r => r.data),
  get: (id: string) => apiClient.get<Project>(`/projects/${id}`).then(r => r.data),
  create: (data: Partial<Project>) => apiClient.post<Project>('/projects', data).then(r => r.data),
  update: (id: string, data: Partial<Project>) =>
    apiClient.patch<Project>(`/projects/${id}`, data).then(r => r.data),
  delete: (id: string) => apiClient.delete(`/projects/${id}`),
  // BOM entries
  listParts: (projectId: string) =>
    apiClient.get<ProjectPart[]>(`/projects/${projectId}/parts`).then(r => r.data),
  addPart: (projectId: string, data: { part_id: string; quantity_required: number; unit?: string; notes?: string }) =>
    apiClient.post<ProjectPart>(`/projects/${projectId}/parts`, data).then(r => r.data),
  updatePart: (projectId: string, entryId: string, data: { quantity_required?: number; unit?: string; notes?: string }) =>
    apiClient.patch<ProjectPart>(`/projects/${projectId}/parts/${entryId}`, data).then(r => r.data),
  removePart: (projectId: string, entryId: string) =>
    apiClient.delete(`/projects/${projectId}/parts/${entryId}`),
  // Availability
  getAvailability: (projectId: string) =>
    apiClient.get<BOMAvailabilityResponse>(`/projects/${projectId}/availability`).then(r => r.data),
}

export interface AIFeatureAssignment {
  feature_key: string
  feature_label: string
  provider_id: string | null
  provider_name: string | null
  updated_at: string
}

export const aiApi = {
  list: () =>
    apiClient.get<AIProviderConfig[]>('/ai/providers').then(r => r.data),
  get: (id: string) =>
    apiClient.get<AIProviderConfig>(`/ai/providers/${id}`).then(r => r.data),
  create: (data: Partial<AIProviderConfig>) =>
    apiClient.post<AIProviderConfig>('/ai/providers', data).then(r => r.data),
  update: (id: string, data: Partial<AIProviderConfig>) =>
    apiClient.patch<AIProviderConfig>(`/ai/providers/${id}`, data).then(r => r.data),
  delete: (id: string) => apiClient.delete(`/ai/providers/${id}`),
  healthCheck: (id: string) =>
    apiClient.post<HealthCheckResponse>(`/ai/providers/${id}/health`).then(r => r.data),
  listFeatureAssignments: () =>
    apiClient.get<AIFeatureAssignment[]>('/ai/feature-assignments').then(r => r.data),
  setFeatureAssignment: (featureKey: string, providerId: string | null) =>
    apiClient
      .put<AIFeatureAssignment>(`/ai/feature-assignments/${featureKey}`, { provider_id: providerId })
      .then(r => r.data),
}

export type EnrichmentJobType =
  | 'summarise_document'
  | 'extract_metadata'
  | 'generate_aliases'
  | 'classify_part'
  | 'enrich_part'

export type EnrichmentEntityType = 'part' | 'document'

export type EnrichmentJobStatus =
  | 'pending'
  | 'running'
  | 'done'
  | 'failed'
  | 'dismissed'

export interface EnrichmentJob {
  id: string
  job_type: EnrichmentJobType
  entity_type: EnrichmentEntityType
  entity_id: string
  status: EnrichmentJobStatus
  provider_id: string | null
  provider_name: string | null
  result_json: Record<string, unknown> | null
  confidence: number | null
  error_message: string | null
  applied_at: string | null
  created_at: string
  updated_at: string
}

export const enrichmentApi = {
  /** Create and immediately run an enrichment job. */
  create: (data: { job_type: EnrichmentJobType; entity_type: EnrichmentEntityType; entity_id: string }) =>
    apiClient.post<EnrichmentJob>('/enrichment/jobs', data).then(r => r.data),

  list: (params?: {
    entity_type?: EnrichmentEntityType
    entity_id?: string
    job_type?: EnrichmentJobType
    status?: EnrichmentJobStatus
    skip?: number
    limit?: number
  }) =>
    apiClient.get<PagedResponse<EnrichmentJob>>('/enrichment/jobs', { params }).then(r => r.data),

  get: (id: string) =>
    apiClient.get<EnrichmentJob>(`/enrichment/jobs/${id}`).then(r => r.data),

  apply: (id: string) =>
    apiClient.post<EnrichmentJob>(`/enrichment/jobs/${id}/apply`).then(r => r.data),

  dismiss: (id: string) =>
    apiClient.post<EnrichmentJob>(`/enrichment/jobs/${id}/dismiss`).then(r => r.data),

  delete: (id: string) =>
    apiClient.delete(`/enrichment/jobs/${id}`),
}

// ---------------------------------------------------------------------------
// Project suggestions (Epic 11)
// ---------------------------------------------------------------------------

export type SuggestionStatus = 'pending' | 'running' | 'done' | 'failed'

export interface SuggestionOwnedPart {
  part_id: string
  part_name: string
}

export interface SuggestionMissingPart {
  name: string
  notes?: string
}

export interface SuggestionIdea {
  title: string
  description: string
  difficulty?: string
  owned_parts?: SuggestionOwnedPart[]
  missing_parts?: SuggestionMissingPart[]
}

export interface ProjectSuggestion {
  id: string
  prompt: string
  status: SuggestionStatus
  provider_id: string | null
  provider_name: string | null
  result_json: { suggestions: SuggestionIdea[] } | null
  error_message: string | null
  created_at: string
  updated_at: string
}

export const suggestionApi = {
  /** Create and immediately run a project suggestion. */
  create: (prompt: string) =>
    apiClient.post<ProjectSuggestion>('/suggestions', { prompt }).then(r => r.data),

  list: (params?: { skip?: number; limit?: number }) =>
    apiClient.get<PagedResponse<ProjectSuggestion>>('/suggestions', { params }).then(r => r.data),

  get: (id: string) =>
    apiClient.get<ProjectSuggestion>(`/suggestions/${id}`).then(r => r.data),

  delete: (id: string) =>
    apiClient.delete(`/suggestions/${id}`),
}

// ---------------------------------------------------------------------------
// Usage History (Epic 12)
// ---------------------------------------------------------------------------

export type UsageActionType =
  | 'allocated'
  | 'used'
  | 'returned'
  | 'consumed'
  | 'tested'
  | 'damaged'

export interface UsageHistoryEvent {
  id: string
  stock_item_id: string | null
  project_id: string | null
  part_id: string | null
  action_type: UsageActionType
  quantity_delta: number | null
  used_at: string
  notes: string | null
  created_at: string
  updated_at: string
}

// ---------------------------------------------------------------------------
// Hygiene dashboard and part merge (Epic 15)
// ---------------------------------------------------------------------------

export interface HygienePartSummary {
  id: string
  part_code: string
  name: string
  status: string
}

export interface SplitStockPart {
  id: string
  part_code: string
  name: string
  status: string
  location_count: number
  locations: string[]
}

export interface DuplicateGroup {
  reason: string
  parts: Array<{
    id: string
    part_code: string
    name: string
    manufacturer: string | null
    manufacturer_part_number: string | null
    status: string
  }>
}

export interface HygieneDashboard {
  parts_missing_documents: HygienePartSummary[]
  parts_missing_aliases: HygienePartSummary[]
  parts_missing_capabilities: HygienePartSummary[]
  split_stock_parts: SplitStockPart[]
  duplicate_groups: DuplicateGroup[]
}

export interface MergeResponse {
  target_part_id: string
  source_part_id: string
  stock_items_moved: number
  document_links_moved: number
  aliases_moved: number
  project_parts_moved: number
  source_archived: boolean
}

export const hygieneApi = {
  getDashboard: () =>
    apiClient.get<HygieneDashboard>('/hygiene/dashboard').then(r => r.data),
  mergePart: (sourcePartId: string, targetPartId: string) =>
    apiClient
      .post<MergeResponse>(`/parts/${sourcePartId}/merge`, { target_part_id: targetPartId })
      .then(r => r.data),
}


export interface IntakeCandidate {
  part_id: string
  part_code: string
  name: string
  short_description: string | null
  manufacturer: string | null
  manufacturer_part_number: string | null
  part_kind: string | null
  confidence: number
  match_reason: string
}

export interface StorageSuggestion {
  location_id: string | null
  container_id: string | null
  name: string
  score: number
  reason: string
}

export interface IntakeMatchResponse {
  description: string
  normalised_tokens: string[]
  candidates: IntakeCandidate[]
  suggested_part_code: string
  storage_suggestions: StorageSuggestion[]
}

export const intakeApi = {
  match: (description: string, category_id?: string | null) =>
    apiClient
      .post<IntakeMatchResponse>('/intake/match', { description, category_id: category_id ?? null })
      .then(r => r.data),
  suggestCode: (description: string) =>
    apiClient
      .post<{ suggested_part_code: string }>('/intake/suggest-code', { description })
      .then(r => r.data),
}

export const usageHistoryApi = {
  list: (params?: {
    stock_item_id?: string
    project_id?: string
    part_id?: string
    action_type?: string
    skip?: number
    limit?: number
  }) =>
    apiClient.get<PagedResponse<UsageHistoryEvent>>('/usage', { params }).then(r => r.data),

  get: (id: string) =>
    apiClient.get<UsageHistoryEvent>(`/usage/${id}`).then(r => r.data),

  create: (data: {
    action_type: UsageActionType
    stock_item_id?: string | null
    project_id?: string | null
    part_id?: string | null
    quantity_delta?: number | null
    used_at?: string | null
    notes?: string | null
  }) => apiClient.post<UsageHistoryEvent>('/usage', data).then(r => r.data),

  delete: (id: string) => apiClient.delete(`/usage/${id}`),
}

