import { useParams, Link, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { partsApi, stockApi, type Part, type StockItem } from '../api/client'

export function PartDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [editing, setEditing] = useState(false)
  const [form, setForm] = useState<Partial<Part>>({})
  const [error, setError] = useState('')

  const { data: part, isLoading } = useQuery({
    queryKey: ['parts', id],
    queryFn: () => partsApi.get(id!),
    enabled: !!id,
  })

  const { data: stockData } = useQuery({
    queryKey: ['stock', 'part', id],
    queryFn: () => stockApi.list({ part_id: id!, limit: 50 }),
    enabled: !!id,
  })

  const updateMutation = useMutation({
    mutationFn: (payload: Partial<Part>) => partsApi.update(id!, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['parts', id] })
      setEditing(false)
      setError('')
    },
    onError: (err: any) => {
      setError(err?.response?.data?.detail ?? 'Update failed')
    },
  })

  const deleteMutation = useMutation({
    mutationFn: () => partsApi.delete(id!),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['parts'] })
      navigate('/parts')
    },
  })

  if (isLoading) return <div className="loading">Loading…</div>
  if (!part) return <div className="empty">Part not found.</div>

  const handleEdit = () => {
    setForm({
      name: part.name,
      short_description: part.short_description ?? '',
      manufacturer: part.manufacturer ?? '',
      manufacturer_part_number: part.manufacturer_part_number ?? '',
      default_unit: part.default_unit,
      package_type: part.package_type ?? '',
      status: part.status,
      notes: part.notes ?? '',
    })
    setEditing(true)
  }

  const handleUpdate = (e: React.FormEvent) => {
    e.preventDefault()
    const payload: Partial<Part> = {}
    for (const [k, v] of Object.entries(form)) {
      if (v !== '') (payload as any)[k] = v
    }
    updateMutation.mutate(payload)
  }

  return (
    <div>
      <div style={{ marginBottom: '1rem' }}>
        <Link to="/parts" style={{ color: '#6b7280', fontSize: '0.875rem' }}>← Parts</Link>
      </div>

      <div className="page-header">
        <div>
          <h1 className="page-title">{part.name}</h1>
          <code style={{ color: '#6b7280', fontSize: '0.9rem' }}>{part.part_code}</code>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button className="btn btn-secondary btn-sm" onClick={handleEdit}>Edit</button>
          <button
            className="btn btn-danger btn-sm"
            onClick={() => { if (confirm('Delete this part?')) deleteMutation.mutate() }}
          >
            Delete
          </button>
        </div>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      {editing ? (
        <div className="card">
          <form onSubmit={handleUpdate}>
            <div className="form-group">
              <label className="form-label">Name</label>
              <input className="form-control" value={form.name ?? ''} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} />
            </div>
            <div className="form-group">
              <label className="form-label">Short Description</label>
              <input className="form-control" value={form.short_description ?? ''} onChange={e => setForm(f => ({ ...f, short_description: e.target.value }))} />
            </div>
            <div className="form-group">
              <label className="form-label">Manufacturer</label>
              <input className="form-control" value={form.manufacturer ?? ''} onChange={e => setForm(f => ({ ...f, manufacturer: e.target.value }))} />
            </div>
            <div className="form-group">
              <label className="form-label">MPN</label>
              <input className="form-control" value={form.manufacturer_part_number ?? ''} onChange={e => setForm(f => ({ ...f, manufacturer_part_number: e.target.value }))} />
            </div>
            <div className="form-group">
              <label className="form-label">Status</label>
              <select className="form-control" value={form.status ?? 'draft'} onChange={e => setForm(f => ({ ...f, status: e.target.value }))}>
                <option value="draft">Draft</option>
                <option value="active">Active</option>
                <option value="archived">Archived</option>
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">Notes</label>
              <textarea className="form-control" rows={3} value={form.notes ?? ''} onChange={e => setForm(f => ({ ...f, notes: e.target.value }))} />
            </div>
            <div className="form-actions">
              <button type="submit" className="btn btn-primary" disabled={updateMutation.isPending}>
                {updateMutation.isPending ? 'Saving…' : 'Save'}
              </button>
              <button type="button" className="btn btn-secondary" onClick={() => setEditing(false)}>Cancel</button>
            </div>
          </form>
        </div>
      ) : (
        <div className="card">
          <table style={{ width: 'auto', fontSize: '0.9rem' }}>
            <tbody>
              {[
                ['Status', <span className={`badge badge-${part.status}`}>{part.status}</span>],
                ['Kind', part.part_kind ?? '—'],
                ['Description', part.short_description ?? '—'],
                ['Manufacturer', part.manufacturer ?? '—'],
                ['MPN', part.manufacturer_part_number ?? '—'],
                ['Default Unit', part.default_unit],
                ['Package', part.package_type ?? '—'],
                ['Spec', part.spec_summary ?? '—'],
                ['Notes', part.notes ?? '—'],
              ].map(([label, value]) => (
                <tr key={label as string}>
                  <td style={{ fontWeight: 500, paddingRight: '2rem', color: '#6b7280', whiteSpace: 'nowrap' }}>{label}</td>
                  <td>{value}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Stock items for this part */}
      <h2 style={{ fontSize: '1.1rem', fontWeight: 600, marginTop: '2rem', marginBottom: '1rem' }}>
        Stock ({stockData?.total ?? 0} item{stockData?.total !== 1 ? 's' : ''})
      </h2>
      {!stockData || stockData.items.length === 0 ? (
        <div className="empty" style={{ padding: '1.5rem' }}>No stock recorded for this part.</div>
      ) : (
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Qty</th>
                <th>Unit</th>
                <th>Status</th>
                <th>Location / Container</th>
                <th>Supplier</th>
              </tr>
            </thead>
            <tbody>
              {stockData.items.map((item: StockItem) => (
                <tr key={item.id}>
                  <td style={{ fontWeight: 500 }}>{item.quantity}</td>
                  <td>{item.unit ?? part.default_unit}</td>
                  <td><span className={`badge badge-${item.status}`}>{item.status}</span></td>
                  <td style={{ fontFamily: 'monospace', fontSize: '0.8rem', color: '#6b7280' }}>
                    {item.container_id ?? item.location_id ?? '—'}
                  </td>
                  <td>{item.supplier ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
