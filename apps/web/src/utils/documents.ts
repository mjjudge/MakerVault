/**
 * Shared constants and utility functions for the Documents feature.
 */

export const DOCUMENT_TYPES = [
  'datasheet', 'manual', 'pinout', 'schematic', 'vendor_page',
  'receipt', 'photo', 'project_note', 'setup_note', 'firmware_note', 'other',
] as const

export const PART_DOC_RELATIONSHIPS = [
  'primary_datasheet', 'manual', 'pinout', 'schematic', 'supporting_reference', 'other',
] as const

export function formatBytes(bytes: number | null): string {
  if (bytes === null) return '—'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}
