import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  usageHistoryApi,
  partsApi,
  stockApi,
  projectsApi,
  type UsageHistoryEvent,
  type UsageActionType,
  type Part,
  type StockItem,
  type Project,
} from '../api/client'

const ACTION_TYPES: UsageActionType[] = [
  'allocated',
  'used',
  'returned',
  'consumed',
  'tested',
  'damaged',
]

const ACTION_BADGE_CLASS: Record<UsageActionType, string> = {
  allocated: 'badge-reserved',
  used: 'badge-available',
  returned: 'badge-available',
  consumed: 'badge-consumed',
  tested: 'badge-draft',
  damaged: 'badge-missing',
}

function formatDelta(delta: number | null): string {
  if (delta == null) return '—'
  return delta > 0 ? `+${delta}` : String(delta)
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}

export function UsageHistoryPage() {
  const qc = useQueryClient()

  // Filter state
  const [filterActionType, setFilterActionType] = useState('')

  // Record-event form state
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState<{
    action_type: UsageActionType
    stock_item_id: string
    project_id: string
    quantity_delta: string
    notes: string
  }>({
    action_type: 'used',
    stock_item_id: '',
    project_id: '',
    quantity_delta: '',
    notes: '',
  })
  const [formError, setFormError] = useState('')

  // Data queries
  const { data, isLoading } = useQuery({
    queryKey: ['usage', 'list', filterActionType],
    queryFn: () =>
      usageHistoryApi.list({
        action_type: filterActionType || undefined,
        limit: 100,
      }),
  })

  const { data: partsData } = useQuery({
    queryKey: ['parts', 'list', ''],
    queryFn: () => partsApi.list({ limit: 200 }),
  })

  const { data: stockData } = useQuery({
    queryKey: ['stock', 'list'],
    queryFn: () => stockApi.list({ limit: 200 }),
  })

  const { data: projectsData } = useQuery({
    queryKey: ['projects', 'list', ''],
    queryFn: () => projectsApi.list({ limit: 100 }),
  })

  // Build lookup maps
  const partMap = new Map<string, Part>()
  if (partsData) partsData.items.forEach(p => partMap.set(p.id, p))

  const stockMap = new Map<string, StockItem>()
  if (stockData) stockData.items.forEach(s => stockMap.set(s.id, s))

  const projectMap = new Map<string, Project>()
  if (projectsData) projectsData.items.forEach(p => projectMap.set(p.id, p))

  const createMutation = useMutation({
    mutationFn: () =>
      usageHistoryApi.create({
        action_type: form.action_type,
        stock_item_id: form.stock_item_id || null,
        project_id: form.project_id || null,
        quantity_delta: form.quantity_delta !== '' ? parseFloat(form.quantity_delta) : null,
        notes: form.notes || null,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['usage'] })
      qc.invalidateQueries({ queryKey: ['stock'] })
      setShowForm(false)
      setForm({ action_type: 'used', stock_item_id: '', project_id: '', quantity_delta: '', notes: '' })
      setFormError('')
    },
    onError: (err: any) => {
      setFormError(err?.response?.data?.detail ?? 'Failed to record event')
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => usageHistoryApi.delete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['usage'] })
    },
  })

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setFormError('')
    createMutation.mutate()
  }

  function partName(event: UsageHistoryEvent): string {
    if (event.part_id) {
      const p = partMap.get(event.part_id)
      if (p) return p.name
    }
    if (event.stock_item_id) {
      const s = stockMap.get(event.stock_item_id)
      if (s) {
        const p = partMap.get(s.part_id)
        if (p) return p.name
      }
    }
    return event.part_id ? `${event.part_id.slice(0, 8)}…` : '—'
  }

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Usage History</h1>
        <button className="btn-primary" onClick={() => setShowForm(v => !v)}>
          {showForm ? 'Cancel' : '+ Record Event'}
        </button>
      </div>

      {/* Record event form */}
      {showForm && (
        <div className="form-card" style={{ marginBottom: '1.5rem' }}>
          <h2 style={{ fontSize: '1rem', marginBottom: '1rem' }}>Record a Usage Event</h2>
          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
              <div style={{ flex: '1 1 180px' }}>
                <label style={{ display: 'block', marginBottom: '0.25rem', fontSize: '0.875rem' }}>
                  Action type *
                </label>
                <select
                  value={form.action_type}
                  onChange={e => setForm(f => ({ ...f, action_type: e.target.value as UsageActionType }))}
                  required
                  style={{ width: '100%' }}
                >
                  {ACTION_TYPES.map(a => (
                    <option key={a} value={a}>{a}</option>
                  ))}
                </select>
              </div>

              <div style={{ flex: '2 1 240px' }}>
                <label style={{ display: 'block', marginBottom: '0.25rem', fontSize: '0.875rem' }}>
                  Stock item
                </label>
                <select
                  value={form.stock_item_id}
                  onChange={e => setForm(f => ({ ...f, stock_item_id: e.target.value }))}
                  style={{ width: '100%' }}
                >
                  <option value="">— none —</option>
                  {stockData?.items.map(s => {
                    const p = partMap.get(s.part_id)
                    const label = p ? `${p.name} (qty: ${s.quantity})` : s.id.slice(0, 8)
                    return <option key={s.id} value={s.id}>{label}</option>
                  })}
                </select>
              </div>

              <div style={{ flex: '2 1 240px' }}>
                <label style={{ display: 'block', marginBottom: '0.25rem', fontSize: '0.875rem' }}>
                  Project (optional)
                </label>
                <select
                  value={form.project_id}
                  onChange={e => setForm(f => ({ ...f, project_id: e.target.value }))}
                  style={{ width: '100%' }}
                >
                  <option value="">— none —</option>
                  {projectsData?.items.map(p => (
                    <option key={p.id} value={p.id}>{p.name}</option>
                  ))}
                </select>
              </div>

              <div style={{ flex: '1 1 120px' }}>
                <label style={{ display: 'block', marginBottom: '0.25rem', fontSize: '0.875rem' }}>
                  Quantity delta
                </label>
                <input
                  type="number"
                  step="any"
                  placeholder="e.g. -3 or +5"
                  value={form.quantity_delta}
                  onChange={e => setForm(f => ({ ...f, quantity_delta: e.target.value }))}
                  style={{ width: '100%' }}
                />
              </div>
            </div>

            <div>
              <label style={{ display: 'block', marginBottom: '0.25rem', fontSize: '0.875rem' }}>
                Notes
              </label>
              <input
                type="text"
                placeholder="Optional notes"
                value={form.notes}
                onChange={e => setForm(f => ({ ...f, notes: e.target.value }))}
                style={{ width: '100%' }}
              />
            </div>

            {formError && <p className="error-text">{formError}</p>}

            <div>
              <button type="submit" className="btn-primary" disabled={createMutation.isPending}>
                {createMutation.isPending ? 'Saving…' : 'Record Event'}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Filter bar */}
      <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '1rem', alignItems: 'center' }}>
        <label style={{ fontSize: '0.875rem' }}>Filter by action:</label>
        <select
          value={filterActionType}
          onChange={e => setFilterActionType(e.target.value)}
        >
          <option value="">All</option>
          {ACTION_TYPES.map(a => (
            <option key={a} value={a}>{a}</option>
          ))}
        </select>
      </div>

      {isLoading ? (
        <div className="loading">Loading usage history…</div>
      ) : !data || data.items.length === 0 ? (
        <div className="empty">
          No usage events recorded yet. Use the "Record Event" button above to start tracking stock changes.
        </div>
      ) : (
        <div className="table-container">
          <p style={{ marginBottom: '0.5rem', fontSize: '0.85rem', color: '#6b7280' }}>
            {data.total} event{data.total !== 1 ? 's' : ''}
            {filterActionType ? ` · filtered by "${filterActionType}"` : ''}
          </p>
          <table>
            <thead>
              <tr>
                <th>When</th>
                <th>Action</th>
                <th>Part</th>
                <th>Delta</th>
                <th>Project</th>
                <th>Notes</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((event: UsageHistoryEvent) => {
                const project = event.project_id ? projectMap.get(event.project_id) : null
                return (
                  <tr key={event.id}>
                    <td style={{ fontSize: '0.8rem', whiteSpace: 'nowrap' }}>
                      {formatDate(event.used_at)}
                    </td>
                    <td>
                      <span className={`badge ${ACTION_BADGE_CLASS[event.action_type] ?? ''}`}>
                        {event.action_type}
                      </span>
                    </td>
                    <td>{partName(event)}</td>
                    <td style={{ fontFamily: 'monospace', fontWeight: 500 }}>
                      {formatDelta(event.quantity_delta)}
                    </td>
                    <td>{project ? project.name : '—'}</td>
                    <td style={{ fontSize: '0.85rem', color: '#6b7280' }}>{event.notes ?? '—'}</td>
                    <td>
                      <button
                        className="btn-danger btn-sm"
                        onClick={() => {
                          if (confirm('Delete this usage event?')) {
                            deleteMutation.mutate(event.id)
                          }
                        }}
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
