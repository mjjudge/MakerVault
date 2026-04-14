/**
 * HygienePage — Inventory hygiene dashboard (Epic 15)
 *
 * Shows:
 *  - Summary cards with counts for each issue category
 *  - "Possible duplicates" review queue with a Merge workflow
 *  - "Split stock" parts (stock stored in multiple locations)
 *  - Parts missing documents
 *  - Parts missing aliases / capabilities
 */

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  hygieneApi,
  type HygienePartSummary,
  type SplitStockPart,
  type DuplicateGroup,
} from '../api/client'

// ---------------------------------------------------------------------------
// Merge dialog
// ---------------------------------------------------------------------------

interface MergeDialogProps {
  group: DuplicateGroup
  onClose: () => void
}

function MergeDialog({ group, onClose }: MergeDialogProps) {
  const queryClient = useQueryClient()
  const [keepId, setKeepId] = useState<string>(group.parts[0].id)
  const [mergeId, setMergeId] = useState<string>(group.parts[1]?.id ?? '')
  const [result, setResult] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: () => hygieneApi.mergePart(mergeId, keepId),
    onSuccess: (data) => {
      setResult(
        `Merged: ${data.stock_items_moved} stock items, ` +
        `${data.document_links_moved} document links, ` +
        `${data.aliases_moved} aliases, ` +
        `${data.project_parts_moved} project parts moved to the canonical part. ` +
        `Source archived.`
      )
      queryClient.invalidateQueries({ queryKey: ['hygiene'] })
    },
    onError: (err: any) => {
      setError(err?.response?.data?.detail ?? 'Merge failed. Please try again.')
    },
  })

  const otherOptions = group.parts.filter(p => p.id !== keepId)

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.45)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
      }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <div
        style={{
          background: '#fff',
          borderRadius: '8px',
          padding: '1.5rem',
          maxWidth: '560px',
          width: '100%',
          boxShadow: '0 8px 32px rgba(0,0,0,0.18)',
        }}
      >
        <h2 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '1rem' }}>
          Merge duplicate parts
        </h2>

        {result ? (
          <div>
            <div className="alert" style={{ background: '#dcfce7', color: '#166534', border: '1px solid #bbf7d0', borderRadius: '6px', padding: '0.75rem 1rem', marginBottom: '1rem' }}>
              ✅ {result}
            </div>
            <button className="btn btn-primary" onClick={onClose}>Done</button>
          </div>
        ) : (
          <>
            <p style={{ fontSize: '0.9rem', color: '#6b7280', marginBottom: '1.25rem' }}>
              Choose which part is the <strong>canonical (keep)</strong> record.
              The other part's stock, documents, aliases, and BOM entries will be moved to it, then the source will be archived.
            </p>

            <div style={{ marginBottom: '1rem' }}>
              <label style={{ fontWeight: 600, fontSize: '0.9rem', display: 'block', marginBottom: '0.4rem' }}>
                Keep (canonical)
              </label>
              <select
                className="search-input"
                style={{ width: '100%' }}
                value={keepId}
                onChange={e => {
                  setKeepId(e.target.value)
                  const newMerge = group.parts.find(p => p.id !== e.target.value)
                  if (newMerge) setMergeId(newMerge.id)
                }}
              >
                {group.parts.map(p => (
                  <option key={p.id} value={p.id}>
                    {p.part_code} — {p.name} ({p.status})
                  </option>
                ))}
              </select>
            </div>

            <div style={{ marginBottom: '1.25rem' }}>
              <label style={{ fontWeight: 600, fontSize: '0.9rem', display: 'block', marginBottom: '0.4rem' }}>
                Merge into canonical (will be archived)
              </label>
              <select
                className="search-input"
                style={{ width: '100%' }}
                value={mergeId}
                onChange={e => setMergeId(e.target.value)}
              >
                {otherOptions.map(p => (
                  <option key={p.id} value={p.id}>
                    {p.part_code} — {p.name} ({p.status})
                  </option>
                ))}
              </select>
            </div>

            {error && (
              <div className="alert alert-error" style={{ marginBottom: '1rem' }}>{error}</div>
            )}

            <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
              <button className="btn btn-secondary" onClick={onClose} disabled={mutation.isPending}>
                Cancel
              </button>
              <button
                className="btn btn-primary"
                style={{ background: '#dc2626', borderColor: '#dc2626' }}
                onClick={() => mutation.mutate()}
                disabled={mutation.isPending || keepId === mergeId}
              >
                {mutation.isPending ? 'Merging…' : 'Merge parts'}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Summary card
// ---------------------------------------------------------------------------

function SummaryCard({ label, count, color }: { label: string; count: number; color: string }) {
  return (
    <div
      style={{
        padding: '1rem 1.25rem',
        background: '#fff',
        border: `1px solid ${count === 0 ? '#d1fae5' : '#fde68a'}`,
        borderRadius: '8px',
        minWidth: '160px',
        flex: 1,
      }}
    >
      <div style={{ fontSize: '1.75rem', fontWeight: 700, color }}>{count}</div>
      <div style={{ fontSize: '0.82rem', color: '#6b7280', marginTop: '2px' }}>{label}</div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Part list table
// ---------------------------------------------------------------------------

function PartTable({ parts, emptyMessage }: { parts: HygienePartSummary[]; emptyMessage: string }) {
  const navigate = useNavigate()
  if (parts.length === 0) {
    return <p style={{ color: '#6b7280', fontSize: '0.9rem' }}>{emptyMessage}</p>
  }
  return (
    <div className="table-container">
      <table>
        <thead>
          <tr>
            <th>Part code</th>
            <th>Name</th>
            <th>Status</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {parts.map(p => (
            <tr key={p.id}>
              <td style={{ fontFamily: 'monospace', fontWeight: 500 }}>{p.part_code}</td>
              <td>{p.name}</td>
              <td><StatusBadge status={p.status} /></td>
              <td>
                <button
                  className="btn btn-secondary"
                  style={{ fontSize: '0.8rem', padding: '2px 10px' }}
                  onClick={() => navigate(`/parts/${p.id}`)}
                >
                  View
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Split stock table
// ---------------------------------------------------------------------------

function SplitStockTable({ parts }: { parts: SplitStockPart[] }) {
  const navigate = useNavigate()
  if (parts.length === 0) {
    return <p style={{ color: '#6b7280', fontSize: '0.9rem' }}>✅ No parts with split stock found.</p>
  }
  return (
    <div className="table-container">
      <table>
        <thead>
          <tr>
            <th>Part code</th>
            <th>Name</th>
            <th>Distinct placements</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {parts.map(p => (
            <tr key={p.id}>
              <td style={{ fontFamily: 'monospace', fontWeight: 500 }}>{p.part_code}</td>
              <td>{p.name}</td>
              <td>
                <span style={{ fontWeight: 600, color: '#d97706' }}>{p.location_count}</span>
                <span style={{ fontSize: '0.8rem', color: '#9ca3af', marginLeft: '0.4rem' }}>
                  locations/containers
                </span>
              </td>
              <td>
                <button
                  className="btn btn-secondary"
                  style={{ fontSize: '0.8rem', padding: '2px 10px' }}
                  onClick={() => navigate(`/parts/${p.id}`)}
                >
                  View
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Duplicates section
// ---------------------------------------------------------------------------

function DuplicatesSection({ groups }: { groups: DuplicateGroup[] }) {
  const navigate = useNavigate()
  const [activeGroup, setActiveGroup] = useState<DuplicateGroup | null>(null)

  if (groups.length === 0) {
    return <p style={{ color: '#6b7280', fontSize: '0.9rem' }}>✅ No duplicate groups detected.</p>
  }

  return (
    <>
      {activeGroup && (
        <MergeDialog group={activeGroup} onClose={() => setActiveGroup(null)} />
      )}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
        {groups.map((g, i) => (
          <div
            key={i}
            style={{
              background: '#fff',
              border: '1px solid #fca5a5',
              borderRadius: '8px',
              padding: '0.875rem 1rem',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
              <span style={{ fontSize: '0.78rem', fontWeight: 600, color: '#991b1b', background: '#fee2e2', padding: '2px 8px', borderRadius: '9999px' }}>
                {g.reason === 'same_name' ? 'Same name' : 'Same MPN'}
              </span>
              {g.parts.length === 2 && (
                <button
                  className="btn btn-primary"
                  style={{ fontSize: '0.8rem', padding: '3px 12px', background: '#dc2626', borderColor: '#dc2626' }}
                  onClick={() => setActiveGroup(g)}
                >
                  Merge…
                </button>
              )}
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
              {g.parts.map(p => (
                <span
                  key={p.id}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '0.4rem',
                    background: '#f9fafb',
                    border: '1px solid #e5e7eb',
                    borderRadius: '6px',
                    padding: '3px 10px',
                    fontSize: '0.85rem',
                  }}
                >
                  <span style={{ fontFamily: 'monospace', fontWeight: 500 }}>{p.part_code}</span>
                  <span style={{ color: '#6b7280' }}>{p.name}</span>
                  <button
                    style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0, color: '#6b7280', fontSize: '0.78rem', textDecoration: 'underline' }}
                    onClick={() => navigate(`/parts/${p.id}`)}
                  >
                    view
                  </button>
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>
    </>
  )
}

// ---------------------------------------------------------------------------
// Small helpers
// ---------------------------------------------------------------------------

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, { bg: string; text: string }> = {
    active:   { bg: '#dcfce7', text: '#166534' },
    draft:    { bg: '#fef9c3', text: '#854d0e' },
    archived: { bg: '#f3f4f6', text: '#6b7280' },
  }
  const c = colors[status] ?? { bg: '#f3f4f6', text: '#374151' }
  return (
    <span style={{ background: c.bg, color: c.text, borderRadius: '9999px', padding: '1px 8px', fontSize: '0.75rem', fontWeight: 600 }}>
      {status}
    </span>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export function HygienePage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['hygiene'],
    queryFn: hygieneApi.getDashboard,
  })

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Inventory Hygiene</h1>
      </div>

      <p style={{ marginBottom: '1.5rem', color: '#6b7280', maxWidth: '640px' }}>
        Review and resolve data quality issues in your inventory. Merge duplicate parts, add missing metadata, and consolidate split stock.
      </p>

      {isLoading && <p style={{ color: '#6b7280' }}>Loading…</p>}
      {error && <div className="alert alert-error">Failed to load hygiene data.</div>}

      {data && (
        <>
          {/* Summary cards */}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem', marginBottom: '2rem' }}>
            <SummaryCard
              label="Possible duplicates"
              count={data.duplicate_groups.length}
              color={data.duplicate_groups.length > 0 ? '#dc2626' : '#059669'}
            />
            <SummaryCard
              label="Split stock"
              count={data.split_stock_parts.length}
              color={data.split_stock_parts.length > 0 ? '#d97706' : '#059669'}
            />
            <SummaryCard
              label="Missing documents"
              count={data.parts_missing_documents.length}
              color={data.parts_missing_documents.length > 0 ? '#d97706' : '#059669'}
            />
            <SummaryCard
              label="Missing aliases"
              count={data.parts_missing_aliases.length}
              color={data.parts_missing_aliases.length > 0 ? '#6b7280' : '#059669'}
            />
            <SummaryCard
              label="Missing capabilities"
              count={data.parts_missing_capabilities.length}
              color={data.parts_missing_capabilities.length > 0 ? '#6b7280' : '#059669'}
            />
          </div>

          {/* Duplicate groups */}
          <section style={{ marginBottom: '2.5rem' }}>
            <h2 style={{ fontSize: '1.05rem', fontWeight: 700, marginBottom: '0.75rem' }}>
              🔴 Possible duplicates ({data.duplicate_groups.length})
            </h2>
            <DuplicatesSection groups={data.duplicate_groups} />
          </section>

          {/* Split stock */}
          <section style={{ marginBottom: '2.5rem' }}>
            <h2 style={{ fontSize: '1.05rem', fontWeight: 700, marginBottom: '0.75rem' }}>
              🟡 Parts with split stock ({data.split_stock_parts.length})
            </h2>
            <p style={{ fontSize: '0.85rem', color: '#6b7280', marginBottom: '0.75rem' }}>
              These parts have active stock stored in more than one location or container.
            </p>
            <SplitStockTable parts={data.split_stock_parts} />
          </section>

          {/* Missing documents */}
          <section style={{ marginBottom: '2.5rem' }}>
            <h2 style={{ fontSize: '1.05rem', fontWeight: 700, marginBottom: '0.75rem' }}>
              📄 Parts missing documents ({data.parts_missing_documents.length})
            </h2>
            <PartTable
              parts={data.parts_missing_documents}
              emptyMessage="✅ All parts have at least one linked document."
            />
          </section>

          {/* Missing aliases */}
          <section style={{ marginBottom: '2.5rem' }}>
            <h2 style={{ fontSize: '1.05rem', fontWeight: 700, marginBottom: '0.75rem' }}>
              🏷️ Parts missing aliases ({data.parts_missing_aliases.length})
            </h2>
            <PartTable
              parts={data.parts_missing_aliases}
              emptyMessage="✅ All parts have at least one alias."
            />
          </section>

          {/* Missing capabilities */}
          <section style={{ marginBottom: '2.5rem' }}>
            <h2 style={{ fontSize: '1.05rem', fontWeight: 700, marginBottom: '0.75rem' }}>
              ⚙️ Parts missing capabilities ({data.parts_missing_capabilities.length})
            </h2>
            <PartTable
              parts={data.parts_missing_capabilities}
              emptyMessage="✅ All parts have capabilities data."
            />
          </section>
        </>
      )}
    </div>
  )
}
