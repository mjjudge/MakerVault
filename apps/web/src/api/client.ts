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


export interface StockItem {
  id: string
  part_id: string
  location_id: string | null
  container_id: string | null
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
}

export const stockApi = {
  list: (params?: { part_id?: string; location_id?: string; container_id?: string; skip?: number; limit?: number }) =>
    apiClient.get<PagedResponse<StockItem>>('/stock', { params }).then(r => r.data),
  get: (id: string) => apiClient.get<StockItem>(`/stock/${id}`).then(r => r.data),
  create: (data: Partial<StockItem>) => apiClient.post<StockItem>('/stock', data).then(r => r.data),
  update: (id: string, data: Partial<StockItem>) =>
    apiClient.patch<StockItem>(`/stock/${id}`, data).then(r => r.data),
  delete: (id: string) => apiClient.delete(`/stock/${id}`),
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
  list: (params?: { location_id?: string; skip?: number; limit?: number }) =>
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
