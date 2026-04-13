import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { locationsApi, containersApi, type Location, type Container } from '../api/client'

export function LocationsPage() {
  const qc = useQueryClient()
  const [showLocModal, setShowLocModal] = useState(false)
  const [showCtrModal, setShowCtrModal] = useState(false)
  const [locForm, setLocForm] = useState({ name: '' })
  const [ctrForm, setCtrForm] = useState({ name: '', location_id: '' })
  const [error, setError] = useState('')

  const { data: locsData, isLoading: locsLoading } = useQuery({
    queryKey: ['locations', 'list'],
    queryFn: () => locationsApi.list({ limit: 100 }),
  })

  const { data: ctrsData } = useQuery({
    queryKey: ['containers', 'list'],
    queryFn: () => containersApi.list({ limit: 100 }),
  })

  const createLocMutation = useMutation({
    mutationFn: (payload: Partial<Location>) => locationsApi.create(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['locations'] })
      setShowLocModal(false)
      setLocForm({ name: '' })
      setError('')
    },
    onError: (err: any) => setError(err?.response?.data?.detail ?? 'Failed'),
  })

  const createCtrMutation = useMutation({
    mutationFn: (payload: Partial<Container>) => containersApi.create(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['containers'] })
      setShowCtrModal(false)
      setCtrForm({ name: '', location_id: '' })
      setError('')
    },
    onError: (err: any) => setError(err?.response?.data?.detail ?? 'Failed'),
  })

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Locations &amp; Containers</h1>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button className="btn btn-secondary" onClick={() => setShowCtrModal(true)}>+ Container</button>
          <button className="btn btn-primary" onClick={() => setShowLocModal(true)}>+ Location</button>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2rem' }}>
        {/* Locations */}
        <div>
          <h2 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '0.75rem', color: '#374151' }}>
            Locations ({locsData?.total ?? 0})
          </h2>
          {locsLoading ? (
            <div className="loading">Loading…</div>
          ) : !locsData || locsData.items.length === 0 ? (
            <div className="empty" style={{ padding: '1.5rem' }}>No locations yet.</div>
          ) : (
            <div>
              {locsData.items.map((loc: Location) => (
                <div key={loc.id} className="card" style={{ marginBottom: '0.5rem' }}>
                  <div style={{ fontWeight: 500 }}>{loc.name}</div>
                  {loc.description && (
                    <div style={{ fontSize: '0.8rem', color: '#6b7280', marginTop: '0.25rem' }}>{loc.description}</div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Containers */}
        <div>
          <h2 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '0.75rem', color: '#374151' }}>
            Containers ({ctrsData?.total ?? 0})
          </h2>
          {!ctrsData || ctrsData.items.length === 0 ? (
            <div className="empty" style={{ padding: '1.5rem' }}>No containers yet.</div>
          ) : (
            <div>
              {ctrsData.items.map((ctr: Container) => (
                <div key={ctr.id} className="card" style={{ marginBottom: '0.5rem' }}>
                  <div style={{ fontWeight: 500 }}>{ctr.name}</div>
                  {ctr.label_code && (
                    <code style={{ fontSize: '0.75rem', color: '#6b7280' }}>{ctr.label_code}</code>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Create location modal */}
      {showLocModal && (
        <div className="modal-overlay" onClick={() => setShowLocModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-title">New Location</div>
            {error && <div className="alert alert-error">{error}</div>}
            <form onSubmit={e => { e.preventDefault(); createLocMutation.mutate(locForm) }}>
              <div className="form-group">
                <label className="form-label">Name *</label>
                <input
                  className="form-control"
                  required
                  value={locForm.name}
                  onChange={e => setLocForm(f => ({ ...f, name: e.target.value }))}
                  placeholder="Garage"
                />
              </div>
              <div className="form-actions">
                <button type="submit" className="btn btn-primary" disabled={createLocMutation.isPending}>
                  {createLocMutation.isPending ? 'Creating…' : 'Create'}
                </button>
                <button type="button" className="btn btn-secondary" onClick={() => setShowLocModal(false)}>Cancel</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Create container modal */}
      {showCtrModal && (
        <div className="modal-overlay" onClick={() => setShowCtrModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-title">New Container</div>
            {error && <div className="alert alert-error">{error}</div>}
            <form onSubmit={e => { e.preventDefault(); createCtrMutation.mutate({ name: ctrForm.name, location_id: ctrForm.location_id || undefined }) }}>
              <div className="form-group">
                <label className="form-label">Name *</label>
                <input
                  className="form-control"
                  required
                  value={ctrForm.name}
                  onChange={e => setCtrForm(f => ({ ...f, name: e.target.value }))}
                  placeholder="Box A"
                />
              </div>
              <div className="form-group">
                <label className="form-label">Location *</label>
                <select
                  className="form-control"
                  required
                  value={ctrForm.location_id}
                  onChange={e => setCtrForm(f => ({ ...f, location_id: e.target.value }))}
                >
                  <option value="">Select location…</option>
                  {locsData?.items.map((loc: Location) => (
                    <option key={loc.id} value={loc.id}>{loc.name}</option>
                  ))}
                </select>
              </div>
              <div className="form-actions">
                <button type="submit" className="btn btn-primary" disabled={createCtrMutation.isPending}>
                  {createCtrMutation.isPending ? 'Creating…' : 'Create'}
                </button>
                <button type="button" className="btn btn-secondary" onClick={() => setShowCtrModal(false)}>Cancel</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
