/**
 * EnrichmentPanel
 *
 * Shows existing enrichment jobs for a given entity and lets the user trigger
 * new ones.  Supports all four job types; the available types are filtered by
 * entity_type ('part' or 'document').
 *
 * Each job card shows:
 *  - job_type + status badge
 *  - provider name + confidence (if available)
 *  - a collapsible preview of result_json
 *  - Apply / Dismiss / Delete actions (state-dependent)
 *  - error_message when status === 'failed'
 */

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  enrichmentApi,
  type EnrichmentJob,
  type EnrichmentJobType,
  type EnrichmentEntityType,
} from '../api/client'

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const PART_JOB_TYPES: { value: EnrichmentJobType; label: string }[] = [
  { value: 'classify_part', label: 'Classify part' },
  { value: 'generate_aliases', label: 'Generate aliases' },
]

const DOCUMENT_JOB_TYPES: { value: EnrichmentJobType; label: string }[] = [
  { value: 'summarise_document', label: 'Summarise document' },
  { value: 'extract_metadata', label: 'Extract metadata' },
]

const STATUS_COLORS: Record<string, string> = {
  pending: '#d97706',
  running: '#2563eb',
  done: '#059669',
  failed: '#dc2626',
  dismissed: '#9ca3af',
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface EnrichmentPanelProps {
  entityType: EnrichmentEntityType
  entityId: string
  /** Called after a result is applied so the parent can refresh its data. */
  onApplied?: () => void
}

// ---------------------------------------------------------------------------
// Helper components
// ---------------------------------------------------------------------------

function ResultPreview({ result }: { result: Record<string, unknown> }) {
  const [open, setOpen] = useState(false)
  return (
    <div style={{ marginTop: '0.5rem' }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          color: '#6b7280',
          fontSize: '0.78rem',
          padding: 0,
        }}
      >
        {open ? '▾ Hide result' : '▸ Show result'}
      </button>
      {open && (
        <pre
          style={{
            marginTop: '0.4rem',
            padding: '0.6rem',
            background: '#f9fafb',
            border: '1px solid #e5e7eb',
            borderRadius: '4px',
            fontSize: '0.75rem',
            overflowX: 'auto',
            maxHeight: '200px',
            overflowY: 'auto',
          }}
        >
          {JSON.stringify(result, null, 2)}
        </pre>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// EnrichmentJobCard
// ---------------------------------------------------------------------------

function EnrichmentJobCard({
  job,
  onApplied,
  onDismissed,
  onDeleted,
}: {
  job: EnrichmentJob
  onApplied: () => void
  onDismissed: () => void
  onDeleted: () => void
}) {
  const applyMutation = useMutation({
    mutationFn: () => enrichmentApi.apply(job.id),
    onSuccess: () => onApplied(),
  })

  const dismissMutation = useMutation({
    mutationFn: () => enrichmentApi.dismiss(job.id),
    onSuccess: () => onDismissed(),
  })

  const deleteMutation = useMutation({
    mutationFn: () => enrichmentApi.delete(job.id),
    onSuccess: () => onDeleted(),
  })

  const statusColor = STATUS_COLORS[job.status] ?? '#6b7280'

  return (
    <div
      style={{
        border: '1px solid #e5e7eb',
        borderRadius: '6px',
        padding: '0.9rem 1rem',
        marginBottom: '0.6rem',
        background: '#fff',
      }}
    >
      {/* Header row */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', flexWrap: 'wrap' }}>
        <span style={{ fontWeight: 600, fontSize: '0.88rem' }}>
          {job.job_type.replace(/_/g, ' ')}
        </span>
        <span
          style={{
            fontSize: '0.72rem',
            fontWeight: 700,
            color: statusColor,
            textTransform: 'uppercase',
            letterSpacing: '0.04em',
          }}
        >
          {job.status}
        </span>
        {job.provider_name && (
          <span style={{ fontSize: '0.75rem', color: '#6b7280' }}>
            via {job.provider_name}
          </span>
        )}
        {job.confidence !== null && (
          <span style={{ fontSize: '0.75rem', color: '#059669' }}>
            {job.confidence}% confidence
          </span>
        )}
        {job.applied_at && (
          <span style={{ fontSize: '0.72rem', color: '#059669', marginLeft: 'auto' }}>
            ✓ Applied
          </span>
        )}
        {/* delete always available */}
        <button
          onClick={() => {
            if (confirm('Delete this enrichment job record?')) deleteMutation.mutate()
          }}
          style={{
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            color: '#9ca3af',
            fontSize: '0.78rem',
            marginLeft: 'auto',
            padding: 0,
          }}
          title="Delete job"
        >
          ✕
        </button>
      </div>

      {/* Error message */}
      {job.status === 'failed' && job.error_message && (
        <div
          style={{
            marginTop: '0.4rem',
            padding: '0.4rem 0.6rem',
            background: '#fef2f2',
            border: '1px solid #fecaca',
            borderRadius: '4px',
            fontSize: '0.78rem',
            color: '#b91c1c',
          }}
        >
          {job.error_message}
        </div>
      )}

      {/* Result preview */}
      {job.result_json && <ResultPreview result={job.result_json} />}

      {/* Actions */}
      {job.status === 'done' && !job.applied_at && (
        <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.6rem' }}>
          <button
            className="btn btn-primary btn-sm"
            disabled={applyMutation.isPending}
            onClick={() => applyMutation.mutate()}
          >
            {applyMutation.isPending ? 'Applying…' : 'Apply'}
          </button>
          <button
            className="btn btn-secondary btn-sm"
            disabled={dismissMutation.isPending}
            onClick={() => dismissMutation.mutate()}
          >
            {dismissMutation.isPending ? '…' : 'Dismiss'}
          </button>
        </div>
      )}

      {applyMutation.isError && (
        <div style={{ color: '#dc2626', fontSize: '0.78rem', marginTop: '0.3rem' }}>
          Apply failed — {(applyMutation.error as any)?.response?.data?.detail ?? 'unknown error'}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main panel
// ---------------------------------------------------------------------------

export function EnrichmentPanel({ entityType, entityId, onApplied }: EnrichmentPanelProps) {
  const qc = useQueryClient()
  const [selectedJobType, setSelectedJobType] = useState<EnrichmentJobType>(
    entityType === 'part' ? 'classify_part' : 'summarise_document'
  )
  const [runError, setRunError] = useState('')

  const availableJobTypes = entityType === 'part' ? PART_JOB_TYPES : DOCUMENT_JOB_TYPES

  const queryKey = ['enrichment-jobs', entityType, entityId]

  const { data, isLoading, refetch } = useQuery({
    queryKey,
    queryFn: () =>
      enrichmentApi.list({ entity_type: entityType, entity_id: entityId, limit: 20 }),
    enabled: !!entityId,
  })

  const createMutation = useMutation({
    mutationFn: () =>
      enrichmentApi.create({
        job_type: selectedJobType,
        entity_type: entityType,
        entity_id: entityId,
      }),
    onSuccess: () => {
      setRunError('')
      refetch()
    },
    onError: (err: any) => {
      setRunError(err?.response?.data?.detail ?? 'Failed to start enrichment job')
    },
  })

  const handleRefresh = () => {
    refetch()
    onApplied?.()
    qc.invalidateQueries({ queryKey: ['parts', entityId] })
    qc.invalidateQueries({ queryKey: ['part-aliases', entityId] })
    qc.invalidateQueries({ queryKey: ['documents', entityId] })
  }

  const jobs = data?.items ?? []

  return (
    <div>
      {/* Trigger row */}
      <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', marginBottom: '1rem' }}>
        <select
          className="form-control"
          style={{ maxWidth: '220px', fontSize: '0.88rem' }}
          value={selectedJobType}
          onChange={e => setSelectedJobType(e.target.value as EnrichmentJobType)}
        >
          {availableJobTypes.map(jt => (
            <option key={jt.value} value={jt.value}>
              {jt.label}
            </option>
          ))}
        </select>
        <button
          className="btn btn-primary btn-sm"
          disabled={createMutation.isPending}
          onClick={() => createMutation.mutate()}
        >
          {createMutation.isPending ? 'Running…' : '▶ Run AI'}
        </button>
      </div>

      {runError && (
        <div className="alert alert-error" style={{ marginBottom: '0.75rem' }}>
          {runError}
        </div>
      )}

      {/* Job list */}
      {isLoading ? (
        <div style={{ color: '#9ca3af', fontSize: '0.85rem' }}>Loading jobs…</div>
      ) : jobs.length === 0 ? (
        <div
          className="empty"
          style={{ padding: '1rem 1.5rem', fontSize: '0.88rem' }}
        >
          No enrichment jobs yet. Run one above to let AI suggest metadata.
        </div>
      ) : (
        jobs.map(job => (
          <EnrichmentJobCard
            key={job.id}
            job={job}
            onApplied={handleRefresh}
            onDismissed={refetch}
            onDeleted={refetch}
          />
        ))
      )}
    </div>
  )
}
