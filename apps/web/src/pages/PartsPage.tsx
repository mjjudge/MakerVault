import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
import { partsApi, intakeApi, type Part, type IntakeCandidate } from '../api/client'

const DEFAULT_FORM = {
  part_code: '',
  name: '',
  short_description: '',
  manufacturer: '',
  status: 'draft',
  default_unit: 'pcs',
}

export function PartsPage() {
  const qc = useQueryClient()
  const [searchParams, setSearchParams] = useSearchParams()
  const [q, setQ] = useState('')
  const [search, setSearch] = useState('')
  const [showModal, setShowModal] = useState(false)
  const [form, setForm] = useState<typeof DEFAULT_FORM>(DEFAULT_FORM)
  const [error, setError] = useState('')
  const [suggestingCode, setSuggestingCode] = useState(false)
  const [codeWarning, setCodeWarning] = useState<IntakeCandidate[] | null>(null)

  // Auto-open create modal when ?new=1 is present (e.g. from Intake page)
  useEffect(() => {
    if (searchParams.get('new') === '1') {
      const preCode = searchParams.get('part_code') ?? ''
      setForm(f => ({ ...f, part_code: preCode }))
      setShowModal(true)
      // Remove query params so a refresh doesn't re-open
      setSearchParams({}, { replace: true })
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const { data, isLoading } = useQuery({
    queryKey: ['parts', 'list', search],
    queryFn: () => partsApi.list({ q: search || undefined, limit: 100 }),
  })

  const createMutation = useMutation({
    mutationFn: (payload: typeof DEFAULT_FORM) => partsApi.create(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['parts'] })
      setShowModal(false)
      setForm(DEFAULT_FORM)
      setError('')
    },
    onError: (err: any) => {
      setError(err?.response?.data?.detail ?? 'Failed to create part')
    },
  })

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    setSearch(q)
  }

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault()
    createMutation.mutate(form)
  }

  const handleSuggestCode = async () => {
    const desc = [form.name, form.short_description].filter(Boolean).join(' ').trim()
    if (!desc) return
    setSuggestingCode(true)
    setCodeWarning(null)
    try {
      const result = await intakeApi.match(desc)
      setForm(f => ({ ...f, part_code: result.suggested_part_code }))
      const highConf = result.candidates.filter(c => c.confidence >= 50)
      if (highConf.length > 0) setCodeWarning(highConf)
    } catch {
      // silently ignore — user can still type a code manually
    } finally {
      setSuggestingCode(false)
    }
  }

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Parts</h1>
        <button className="btn btn-primary" onClick={() => setShowModal(true)}>
          + New Part
        </button>
      </div>

      <form onSubmit={handleSearch} className="search-bar">
        <input
          type="text"
          className="search-input"
          placeholder="Search by name, code, manufacturer, alias…"
          value={q}
          onChange={e => setQ(e.target.value)}
        />
        <button type="submit" className="btn btn-primary">Search</button>
        {search && (
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => { setQ(''); setSearch('') }}
          >
            Clear
          </button>
        )}
      </form>

      {isLoading ? (
        <div className="loading">Loading parts…</div>
      ) : !data || data.items.length === 0 ? (
        <div className="empty">
          {search ? `No parts found for "${search}"` : 'No parts yet. Add your first part!'}
        </div>
      ) : (
        <div className="table-container">
          <p style={{ marginBottom: '0.5rem', fontSize: '0.85rem', color: '#6b7280' }}>
            {data.total} part{data.total !== 1 ? 's' : ''}
          </p>
          <table>
            <thead>
              <tr>
                <th>Part Code</th>
                <th>Name</th>
                <th>Kind</th>
                <th>Manufacturer</th>
                <th>Unit</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((part: Part) => (
                <tr key={part.id}>
                  <td>
                    <Link to={`/parts/${part.id}`} style={{ fontFamily: 'monospace', fontWeight: 500 }}>
                      {part.part_code}
                    </Link>
                  </td>
                  <td>{part.name}</td>
                  <td>{part.part_kind ?? '—'}</td>
                  <td>{part.manufacturer ?? '—'}</td>
                  <td>{part.default_unit}</td>
                  <td><span className={`badge badge-${part.status}`}>{part.status}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Create modal */}
      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-title">New Part</div>
            {error && <div className="alert alert-error">{error}</div>}
            <form onSubmit={handleCreate}>
              <div className="form-group">
                <label className="form-label">Name *</label>
                <input
                  className="form-control"
                  required
                  value={form.name}
                  onChange={e => { setForm(f => ({ ...f, name: e.target.value })); setCodeWarning(null) }}
                  placeholder="ESP32 DevKit V1"
                />
              </div>
              <div className="form-group">
                <label className="form-label">Short Description</label>
                <input
                  className="form-control"
                  value={form.short_description ?? ''}
                  onChange={e => { setForm(f => ({ ...f, short_description: e.target.value })); setCodeWarning(null) }}
                />
              </div>
              <div className="form-group">
                <label className="form-label">Part Code *</label>
                <div style={{ display: 'flex', gap: '0.5rem' }}>
                  <input
                    className="form-control"
                    required
                    value={form.part_code}
                    onChange={e => { setForm(f => ({ ...f, part_code: e.target.value })); setCodeWarning(null) }}
                    placeholder="e.g. ESP32-DEVKIT-V1 or click Suggest →"
                  />
                  <button
                    type="button"
                    className="btn btn-secondary"
                    style={{ whiteSpace: 'nowrap', flexShrink: 0 }}
                    disabled={suggestingCode || !form.name.trim()}
                    onClick={handleSuggestCode}
                    title="Generate a unique code from the name/description and check for similar existing parts"
                  >
                    {suggestingCode ? '…' : 'Suggest'}
                  </button>
                </div>
                {codeWarning && codeWarning.length > 0 && (
                  <div style={{ marginTop: '0.5rem', padding: '0.6rem 0.75rem', background: '#fffbeb', border: '1px solid #fde68a', borderRadius: '6px', fontSize: '0.8rem' }}>
                    <strong style={{ color: '#92400e' }}>⚠ Similar parts already in your database</strong>
                    <ul style={{ margin: '0.3rem 0 0.4rem 1rem', padding: 0, color: '#78350f' }}>
                      {codeWarning.slice(0, 3).map(c => (
                        <li key={c.part_id}>
                          <strong>{c.part_code}</strong> — {c.name}
                          {' '}<span style={{ color: '#b45309' }}>({c.confidence}% match)</span>
                        </li>
                      ))}
                    </ul>
                    <span style={{ color: '#92400e' }}>
                      Check the{' '}
                      <Link to="/intake" style={{ color: '#d97706', fontWeight: 600 }}>Intake page</Link>
                      {' '}to confirm this isn't a duplicate before adding.
                    </span>
                  </div>
                )}
              </div>
              <div className="form-group">
                <label className="form-label">Manufacturer</label>
                <input
                  className="form-control"
                  value={form.manufacturer ?? ''}
                  onChange={e => setForm(f => ({ ...f, manufacturer: e.target.value }))}
                />
              </div>
              <div className="form-group">
                <label className="form-label">Default Unit</label>
                <input
                  className="form-control"
                  value={form.default_unit ?? 'pcs'}
                  onChange={e => setForm(f => ({ ...f, default_unit: e.target.value }))}
                />
              </div>
              <div className="form-group">
                <label className="form-label">Status</label>
                <select
                  className="form-control"
                  value={form.status ?? 'draft'}
                  onChange={e => setForm(f => ({ ...f, status: e.target.value }))}
                >
                  <option value="draft">Draft</option>
                  <option value="active">Active</option>
                  <option value="archived">Archived</option>
                </select>
              </div>
              <div className="form-actions">
                <button type="submit" className="btn btn-primary" disabled={createMutation.isPending}>
                  {createMutation.isPending ? 'Creating…' : 'Create Part'}
                </button>
                <button type="button" className="btn btn-secondary" onClick={() => { setShowModal(false); setError(''); setCodeWarning(null) }}>
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
