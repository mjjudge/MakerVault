import { useMemo, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { locationsApi, containersApi, type Location, type Container } from '../api/client'

// ---------------------------------------------------------------------------
// Tree helpers
// ---------------------------------------------------------------------------

interface ContainerMaps {
  byLocation: Map<string, Container[]>
  byParent: Map<string, Container[]>
}

function buildContainerMaps(containers: Container[]): ContainerMaps {
  const byLocation = new Map<string, Container[]>()
  const byParent = new Map<string, Container[]>()
  for (const c of containers) {
    if (c.location_id) {
      const arr = byLocation.get(c.location_id) ?? []
      arr.push(c)
      byLocation.set(c.location_id, arr)
    } else if (c.parent_container_id) {
      const arr = byParent.get(c.parent_container_id) ?? []
      arr.push(c)
      byParent.set(c.parent_container_id, arr)
    }
  }
  return { byLocation, byParent }
}

// ---------------------------------------------------------------------------
// Recursive container rows
// ---------------------------------------------------------------------------

function ContainerSubtree({
  parentId,
  byParent,
  depth,
  onEdit,
  onDelete,
}: {
  parentId: string
  byParent: Map<string, Container[]>
  depth: number
  onEdit: (c: Container) => void
  onDelete: (c: Container) => void
}) {
  const children = byParent.get(parentId) ?? []
  if (children.length === 0) return null
  return (
    <>
      {children.map(c => (
        <ContainerRow key={c.id} container={c} byParent={byParent} depth={depth} onEdit={onEdit} onDelete={onDelete} />
      ))}
    </>
  )
}

function ContainerRow({
  container,
  byParent,
  depth,
  onEdit,
  onDelete,
}: {
  container: Container
  byParent: Map<string, Container[]>
  depth: number
  onEdit: (c: Container) => void
  onDelete: (c: Container) => void
}) {
  const hasChildren = (byParent.get(container.id) ?? []).length > 0
  const indent = depth * 1.25

  return (
    <>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '0.4rem',
          padding: '0.4rem 0.5rem',
          paddingLeft: `${0.5 + indent}rem`,
          borderBottom: '1px solid #f3f4f6',
        }}
      >
        {depth > 0 && (
          <span style={{ color: '#9ca3af', fontSize: '0.75rem', flexShrink: 0 }}>└─</span>
        )}
        <span style={{ fontSize: '0.85rem' }}>{depth === 0 ? '📦' : '🗂️'}</span>
        <span style={{ fontWeight: depth === 0 ? 500 : 400, fontSize: '0.875rem', flex: 1 }}>
          {container.name}
        </span>
        {container.label_code && (
          <code style={{ fontSize: '0.7rem', color: '#9ca3af', background: '#f9fafb', padding: '0 0.3rem', borderRadius: 3 }}>
            {container.label_code}
          </code>
        )}
        {hasChildren && (
          <span style={{ fontSize: '0.7rem', color: '#6b7280' }}>
            {(byParent.get(container.id) ?? []).length} inside
          </span>
        )}
        <button
          className="btn btn-secondary btn-sm"
          style={{ padding: '0.15rem 0.5rem', fontSize: '0.75rem' }}
          onClick={() => onEdit(container)}
        >
          Edit
        </button>
        <button
          className="btn btn-danger btn-sm"
          style={{ padding: '0.15rem 0.5rem', fontSize: '0.75rem' }}
          onClick={() => onDelete(container)}
        >
          Delete
        </button>
      </div>
      <ContainerSubtree parentId={container.id} byParent={byParent} depth={depth + 1} onEdit={onEdit} onDelete={onDelete} />
    </>
  )
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export function LocationsPage() {
  const qc = useQueryClient()

  // Create modal visibility
  const [showLocModal, setShowLocModal] = useState(false)
  const [showCtrModal, setShowCtrModal] = useState(false)

  // Edit modal state
  const [editingLoc, setEditingLoc] = useState<Location | null>(null)
  const [editingCtr, setEditingCtr] = useState<Container | null>(null)
  const [editLocForm, setEditLocForm] = useState({ name: '', description: '', parent_location_id: '' })
  const [editCtrForm, setEditCtrForm] = useState({
    name: '',
    description: '',
    label_code: '',
    parentType: 'location' as 'location' | 'container',
    location_id: '',
    parent_container_id: '',
  })

  // Location create form
  const [locForm, setLocForm] = useState({ name: '', description: '', parent_location_id: '' })

  // Container create form — parentType drives which parent field is sent
  const [ctrForm, setCtrForm] = useState({
    name: '',
    description: '',
    label_code: '',
    parentType: 'location' as 'location' | 'container',
    location_id: '',
    parent_container_id: '',
  })

  const [error, setError] = useState('')

  // ---------------------------------------------------------------------------
  // Queries
  // ---------------------------------------------------------------------------

  const { data: locsData, isLoading: locsLoading, isError: locsError } = useQuery({
    queryKey: ['locations', 'list'],
    queryFn: () => locationsApi.list({ limit: 100 }),
  })

  const { data: ctrsData, isLoading: ctrsLoading, isError: ctrsError } = useQuery({
    queryKey: ['containers', 'list'],
    queryFn: () => containersApi.list({ limit: 200 }),
  })

  // ---------------------------------------------------------------------------
  // Derived data
  // ---------------------------------------------------------------------------

  const locationMap = useMemo(() => {
    const m = new Map<string, Location>()
    for (const loc of locsData?.items ?? []) m.set(loc.id, loc)
    return m
  }, [locsData])

  const { byLocation, byParent } = useMemo(
    () => buildContainerMaps(ctrsData?.items ?? []),
    [ctrsData],
  )

  // Locations that have at least one top-level container, or are listed
  const locationsWithContainers = useMemo(() => {
    const locIds = new Set(locsData?.items.map(l => l.id) ?? [])
    return Array.from(locIds)
  }, [locsData])

  // Containers with no location and no parent_container_id (orphans — shouldn't exist but guard anyway)
  const orphanContainers = useMemo(
    () => (ctrsData?.items ?? []).filter(c => !c.location_id && !c.parent_container_id),
    [ctrsData],
  )

  // ---------------------------------------------------------------------------
  // Mutations
  // ---------------------------------------------------------------------------

  const createLocMutation = useMutation({
    mutationFn: (payload: Partial<Location>) => locationsApi.create(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['locations'] })
      setShowLocModal(false)
      setLocForm({ name: '', description: '', parent_location_id: '' })
      setError('')
    },
    onError: (err: any) => setError(err?.response?.data?.detail ?? 'Failed to create location'),
  })

  const updateLocMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Partial<Location> }) =>
      locationsApi.update(id, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['locations'] })
      setEditingLoc(null)
      setError('')
    },
    onError: (err: any) => setError(err?.response?.data?.detail ?? 'Failed to update location'),
  })

  const deleteLocMutation = useMutation({
    mutationFn: (id: string) => locationsApi.delete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['locations'] })
      qc.invalidateQueries({ queryKey: ['containers'] })
    },
    onError: (err: any) => alert(err?.response?.data?.detail ?? 'Failed to delete location'),
  })

  const createCtrMutation = useMutation({
    mutationFn: (payload: Partial<Container>) => containersApi.create(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['containers'] })
      setShowCtrModal(false)
      setCtrForm({ name: '', description: '', label_code: '', parentType: 'location', location_id: '', parent_container_id: '' })
      setError('')
    },
    onError: (err: any) => setError(err?.response?.data?.detail ?? 'Failed to create container'),
  })

  const updateCtrMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Partial<Container> }) =>
      containersApi.update(id, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['containers'] })
      setEditingCtr(null)
      setError('')
    },
    onError: (err: any) => setError(err?.response?.data?.detail ?? 'Failed to update container'),
  })

  const deleteCtrMutation = useMutation({
    mutationFn: (id: string) => containersApi.delete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['containers'] })
    },
    onError: (err: any) => alert(err?.response?.data?.detail ?? 'Failed to delete container'),
  })

  // ---------------------------------------------------------------------------
  // Handlers
  // ---------------------------------------------------------------------------

  function handleLocSubmit(e: React.FormEvent) {
    e.preventDefault()
    const payload: Partial<Location> = { name: locForm.name }
    if (locForm.description) payload.description = locForm.description
    if (locForm.parent_location_id) payload.parent_location_id = locForm.parent_location_id
    createLocMutation.mutate(payload)
  }

  function handleEditLocOpen(loc: Location) {
    setEditLocForm({
      name: loc.name,
      description: loc.description ?? '',
      parent_location_id: loc.parent_location_id ?? '',
    })
    setError('')
    setEditingLoc(loc)
  }

  function handleEditLocSubmit(e: React.FormEvent) {
    e.preventDefault()
    const payload: Partial<Location> = { name: editLocForm.name }
    if (editLocForm.description !== '') payload.description = editLocForm.description
    payload.parent_location_id = editLocForm.parent_location_id || null
    updateLocMutation.mutate({ id: editingLoc!.id, payload })
  }

  function handleCtrSubmit(e: React.FormEvent) {
    e.preventDefault()
    const payload: Partial<Container> = { name: ctrForm.name }
    if (ctrForm.description) payload.description = ctrForm.description
    if (ctrForm.label_code) payload.label_code = ctrForm.label_code
    if (ctrForm.parentType === 'location') {
      payload.location_id = ctrForm.location_id
    } else {
      payload.parent_container_id = ctrForm.parent_container_id
    }
    createCtrMutation.mutate(payload)
  }

  function handleEditCtrOpen(ctr: Container) {
    setEditCtrForm({
      name: ctr.name,
      description: ctr.description ?? '',
      label_code: ctr.label_code ?? '',
      parentType: ctr.location_id ? 'location' : 'container',
      location_id: ctr.location_id ?? '',
      parent_container_id: ctr.parent_container_id ?? '',
    })
    setError('')
    setEditingCtr(ctr)
  }

  function handleEditCtrSubmit(e: React.FormEvent) {
    e.preventDefault()
    const payload: Partial<Container> = { name: editCtrForm.name }
    if (editCtrForm.description !== '') payload.description = editCtrForm.description
    payload.label_code = editCtrForm.label_code || null
    if (editCtrForm.parentType === 'location') {
      payload.location_id = editCtrForm.location_id || null
      payload.parent_container_id = null
    } else {
      payload.parent_container_id = editCtrForm.parent_container_id || null
      payload.location_id = null
    }
    updateCtrMutation.mutate({ id: editingCtr!.id, payload })
  }

  function handleDeleteLoc(loc: Location) {
    if (confirm(`Delete location "${loc.name}"? This cannot be undone.`)) {
      deleteLocMutation.mutate(loc.id)
    }
  }

  function handleDeleteCtr(ctr: Container) {
    if (confirm(`Delete container "${ctr.name}"? This cannot be undone.`)) {
      deleteCtrMutation.mutate(ctr.id)
    }
  }

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Locations &amp; Containers</h1>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button className="btn btn-secondary" onClick={() => { setError(''); setShowCtrModal(true) }}>
            + Container
          </button>
          <button className="btn btn-primary" onClick={() => { setError(''); setShowLocModal(true) }}>
            + Location
          </button>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '2rem' }}>

        {/* ------------------------------------------------------------------ */}
        {/* Locations panel                                                      */}
        {/* ------------------------------------------------------------------ */}
        <div>
          <h2 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '0.75rem', color: '#374151' }}>
            Locations ({locsData?.total ?? 0})
          </h2>
          {locsLoading ? (
            <div className="loading">Loading…</div>
          ) : locsError ? (
            <div className="alert alert-error">Failed to load locations.</div>
          ) : !locsData || locsData.items.length === 0 ? (
            <div className="empty" style={{ padding: '1.5rem' }}>No locations yet.</div>
          ) : (
            <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
              {locsData.items.map((loc: Location) => {
                const parent = loc.parent_location_id ? locationMap.get(loc.parent_location_id) : null
                return (
                  <div
                    key={loc.id}
                    style={{
                      padding: '0.5rem 0.75rem',
                      borderBottom: '1px solid #f3f4f6',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.5rem',
                    }}
                  >
                    <span style={{ fontSize: '0.85rem' }}>📍</span>
                    <div style={{ flex: 1 }}>
                      <span style={{ fontWeight: 500, fontSize: '0.875rem' }}>{loc.name}</span>
                      {parent && (
                        <span style={{ fontSize: '0.75rem', color: '#9ca3af', marginLeft: '0.4rem' }}>
                          in {parent.name}
                        </span>
                      )}
                      {loc.description && (
                        <div style={{ fontSize: '0.75rem', color: '#6b7280', marginTop: '0.1rem' }}>
                          {loc.description}
                        </div>
                      )}
                    </div>
                    <span style={{ fontSize: '0.7rem', color: '#d1d5db', flexShrink: 0 }}>
                      {(byLocation.get(loc.id) ?? []).length > 0
                        ? `${(byLocation.get(loc.id) ?? []).length} ctr`
                        : ''}
                    </span>
                    <button
                      className="btn btn-secondary btn-sm"
                      style={{ padding: '0.15rem 0.5rem', fontSize: '0.75rem', flexShrink: 0 }}
                      onClick={() => handleEditLocOpen(loc)}
                    >
                      Edit
                    </button>
                    <button
                      className="btn btn-danger btn-sm"
                      style={{ padding: '0.15rem 0.5rem', fontSize: '0.75rem', flexShrink: 0 }}
                      onClick={() => handleDeleteLoc(loc)}
                    >
                      Delete
                    </button>
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {/* ------------------------------------------------------------------ */}
        {/* Containers panel — hierarchical tree                                */}
        {/* ------------------------------------------------------------------ */}
        <div>
          <h2 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '0.75rem', color: '#374151' }}>
            Containers ({ctrsData?.total ?? 0})
          </h2>
          {ctrsLoading || (ctrsData && ctrsData.items.length > 0 && locsLoading) ? (
            <div className="loading">Loading…</div>
          ) : ctrsError ? (
            <div className="alert alert-error">Failed to load containers.</div>
          ) : !ctrsData || ctrsData.items.length === 0 ? (
            <div className="empty" style={{ padding: '1.5rem' }}>No containers yet.</div>
          ) : (
            <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
              {/* Render containers grouped under each location */}
              {locationsWithContainers.map(locId => {
                const loc = locationMap.get(locId)
                const topLevel = byLocation.get(locId) ?? []
                if (topLevel.length === 0) return null
                return (
                  <div key={locId}>
                    <div
                      style={{
                        padding: '0.4rem 0.5rem',
                        background: '#f9fafb',
                        borderBottom: '1px solid #e5e7eb',
                        fontSize: '0.75rem',
                        fontWeight: 600,
                        color: '#6b7280',
                        textTransform: 'uppercase',
                        letterSpacing: '0.05em',
                      }}
                    >
                      📍 {loc?.name ?? locId}
                    </div>
                    {topLevel.map(c => (
                      <ContainerRow key={c.id} container={c} byParent={byParent} depth={0} onEdit={handleEditCtrOpen} onDelete={handleDeleteCtr} />
                    ))}
                  </div>
                )
              })}
              {/* Orphaned containers (no location, no parent — data integrity edge case) */}
              {orphanContainers.length > 0 && (
                <div>
                  <div style={{ padding: '0.4rem 0.5rem', background: '#fef9f0', fontSize: '0.75rem', color: '#92400e', borderBottom: '1px solid #fde68a' }}>
                    ⚠ Unassigned
                  </div>
                  {orphanContainers.map(c => (
                    <ContainerRow key={c.id} container={c} byParent={byParent} depth={0} onEdit={handleEditCtrOpen} onDelete={handleDeleteCtr} />
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* -------------------------------------------------------------------- */}
      {/* Create Location modal                                                  */}
      {/* -------------------------------------------------------------------- */}
      {showLocModal && (
        <div className="modal-overlay" onClick={() => setShowLocModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-title">New Location</div>
            {error && <div className="alert alert-error">{error}</div>}
            <form onSubmit={handleLocSubmit}>
              <div className="form-group">
                <label className="form-label">Name *</label>
                <input
                  className="form-control"
                  required
                  value={locForm.name}
                  onChange={e => setLocForm(f => ({ ...f, name: e.target.value }))}
                  placeholder="e.g. Loft, Garage, Workshop"
                />
              </div>
              <div className="form-group">
                <label className="form-label">Description</label>
                <input
                  className="form-control"
                  value={locForm.description}
                  onChange={e => setLocForm(f => ({ ...f, description: e.target.value }))}
                  placeholder="Optional notes"
                />
              </div>
              {locsData && locsData.items.length > 0 && (
                <div className="form-group">
                  <label className="form-label">Inside location (optional)</label>
                  <select
                    className="form-control"
                    value={locForm.parent_location_id}
                    onChange={e => setLocForm(f => ({ ...f, parent_location_id: e.target.value }))}
                  >
                    <option value="">— top-level location —</option>
                    {locsData.items.map((loc: Location) => (
                      <option key={loc.id} value={loc.id}>{loc.name}</option>
                    ))}
                  </select>
                </div>
              )}
              <div className="form-actions">
                <button type="submit" className="btn btn-primary" disabled={createLocMutation.isPending}>
                  {createLocMutation.isPending ? 'Creating…' : 'Create'}
                </button>
                <button type="button" className="btn btn-secondary" onClick={() => setShowLocModal(false)}>
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* -------------------------------------------------------------------- */}
      {/* Edit Location modal                                                    */}
      {/* -------------------------------------------------------------------- */}
      {editingLoc && (
        <div className="modal-overlay" onClick={() => setEditingLoc(null)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-title">Edit Location</div>
            {error && <div className="alert alert-error">{error}</div>}
            <form onSubmit={handleEditLocSubmit}>
              <div className="form-group">
                <label className="form-label">Name *</label>
                <input
                  className="form-control"
                  required
                  value={editLocForm.name}
                  onChange={e => setEditLocForm(f => ({ ...f, name: e.target.value }))}
                />
              </div>
              <div className="form-group">
                <label className="form-label">Description</label>
                <input
                  className="form-control"
                  value={editLocForm.description}
                  onChange={e => setEditLocForm(f => ({ ...f, description: e.target.value }))}
                />
              </div>
              <div className="form-group">
                <label className="form-label">Inside location (optional)</label>
                <select
                  className="form-control"
                  value={editLocForm.parent_location_id}
                  onChange={e => setEditLocForm(f => ({ ...f, parent_location_id: e.target.value }))}
                >
                  <option value="">— top-level location —</option>
                  {locsData?.items
                    .filter(l => l.id !== editingLoc.id)
                    .map((loc: Location) => (
                      <option key={loc.id} value={loc.id}>{loc.name}</option>
                    ))}
                </select>
              </div>
              <div className="form-actions">
                <button type="submit" className="btn btn-primary" disabled={updateLocMutation.isPending}>
                  {updateLocMutation.isPending ? 'Saving…' : 'Save'}
                </button>
                <button type="button" className="btn btn-secondary" onClick={() => setEditingLoc(null)}>
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* -------------------------------------------------------------------- */}
      {/* Create Container modal                                                 */}
      {/* -------------------------------------------------------------------- */}
      {showCtrModal && (
        <div className="modal-overlay" onClick={() => setShowCtrModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-title">New Container</div>
            {error && <div className="alert alert-error">{error}</div>}
            <form onSubmit={handleCtrSubmit}>
              <div className="form-group">
                <label className="form-label">Name *</label>
                <input
                  className="form-control"
                  required
                  value={ctrForm.name}
                  onChange={e => setCtrForm(f => ({ ...f, name: e.target.value }))}
                  placeholder="e.g. Big Box, Sensors Tray"
                />
              </div>
              <div className="form-group">
                <label className="form-label">Description</label>
                <input
                  className="form-control"
                  value={ctrForm.description}
                  onChange={e => setCtrForm(f => ({ ...f, description: e.target.value }))}
                  placeholder="Optional notes"
                />
              </div>
              <div className="form-group">
                <label className="form-label">Label code</label>
                <input
                  className="form-control"
                  value={ctrForm.label_code}
                  onChange={e => setCtrForm(f => ({ ...f, label_code: e.target.value }))}
                  placeholder="e.g. BOX-A1 (optional, must be unique)"
                />
              </div>

              {/* Parent type toggle */}
              <div className="form-group">
                <label className="form-label">Stored in *</label>
                <div style={{ display: 'flex', gap: '1rem', marginBottom: '0.5rem' }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', cursor: 'pointer', fontSize: '0.875rem' }}>
                    <input
                      type="radio"
                      name="parentType"
                      value="location"
                      checked={ctrForm.parentType === 'location'}
                      onChange={() => setCtrForm(f => ({ ...f, parentType: 'location', parent_container_id: '' }))}
                    />
                    A location
                  </label>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', cursor: 'pointer', fontSize: '0.875rem' }}>
                    <input
                      type="radio"
                      name="parentType"
                      value="container"
                      checked={ctrForm.parentType === 'container'}
                      onChange={() => setCtrForm(f => ({ ...f, parentType: 'container', location_id: '' }))}
                    />
                    Another container
                  </label>
                </div>

                {ctrForm.parentType === 'location' ? (
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
                ) : (
                  <select
                    className="form-control"
                    required
                    value={ctrForm.parent_container_id}
                    onChange={e => setCtrForm(f => ({ ...f, parent_container_id: e.target.value }))}
                  >
                    <option value="">Select container…</option>
                    {ctrsData?.items.map((ctr: Container) => {
                      const parentName = ctr.parent_container_id
                        ? ctrsData.items.find(p => p.id === ctr.parent_container_id)?.name
                        : ctr.location_id
                          ? locationMap.get(ctr.location_id)?.name
                          : null
                      return (
                        <option key={ctr.id} value={ctr.id}>
                          {parentName ? `${parentName} › ${ctr.name}` : ctr.name}
                        </option>
                      )
                    })}
                  </select>
                )}
              </div>

              <div className="form-actions">
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={createCtrMutation.isPending}
                >
                  {createCtrMutation.isPending ? 'Creating…' : 'Create'}
                </button>
                <button type="button" className="btn btn-secondary" onClick={() => setShowCtrModal(false)}>
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* -------------------------------------------------------------------- */}
      {/* Edit Container modal                                                   */}
      {/* -------------------------------------------------------------------- */}
      {editingCtr && (
        <div className="modal-overlay" onClick={() => setEditingCtr(null)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-title">Edit Container</div>
            {error && <div className="alert alert-error">{error}</div>}
            <form onSubmit={handleEditCtrSubmit}>
              <div className="form-group">
                <label className="form-label">Name *</label>
                <input
                  className="form-control"
                  required
                  value={editCtrForm.name}
                  onChange={e => setEditCtrForm(f => ({ ...f, name: e.target.value }))}
                />
              </div>
              <div className="form-group">
                <label className="form-label">Description</label>
                <input
                  className="form-control"
                  value={editCtrForm.description}
                  onChange={e => setEditCtrForm(f => ({ ...f, description: e.target.value }))}
                />
              </div>
              <div className="form-group">
                <label className="form-label">Label code</label>
                <input
                  className="form-control"
                  value={editCtrForm.label_code}
                  onChange={e => setEditCtrForm(f => ({ ...f, label_code: e.target.value }))}
                  placeholder="e.g. BOX-A1 (optional, must be unique)"
                />
              </div>
              <div className="form-group">
                <label className="form-label">Stored in</label>
                <div style={{ display: 'flex', gap: '1rem', marginBottom: '0.5rem' }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', cursor: 'pointer', fontSize: '0.875rem' }}>
                    <input
                      type="radio"
                      name="editParentType"
                      value="location"
                      checked={editCtrForm.parentType === 'location'}
                      onChange={() => setEditCtrForm(f => ({ ...f, parentType: 'location', parent_container_id: '' }))}
                    />
                    A location
                  </label>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', cursor: 'pointer', fontSize: '0.875rem' }}>
                    <input
                      type="radio"
                      name="editParentType"
                      value="container"
                      checked={editCtrForm.parentType === 'container'}
                      onChange={() => setEditCtrForm(f => ({ ...f, parentType: 'container', location_id: '' }))}
                    />
                    Another container
                  </label>
                </div>
                {editCtrForm.parentType === 'location' ? (
                  <select
                    className="form-control"
                    value={editCtrForm.location_id}
                    onChange={e => setEditCtrForm(f => ({ ...f, location_id: e.target.value }))}
                  >
                    <option value="">Select location…</option>
                    {locsData?.items.map((loc: Location) => (
                      <option key={loc.id} value={loc.id}>{loc.name}</option>
                    ))}
                  </select>
                ) : (
                  <select
                    className="form-control"
                    value={editCtrForm.parent_container_id}
                    onChange={e => setEditCtrForm(f => ({ ...f, parent_container_id: e.target.value }))}
                  >
                    <option value="">Select container…</option>
                    {ctrsData?.items
                      .filter(c => c.id !== editingCtr.id)
                      .map((ctr: Container) => {
                        const parentName = ctr.parent_container_id
                          ? ctrsData.items.find(p => p.id === ctr.parent_container_id)?.name
                          : ctr.location_id
                            ? locationMap.get(ctr.location_id)?.name
                            : null
                        return (
                          <option key={ctr.id} value={ctr.id}>
                            {parentName ? `${parentName} › ${ctr.name}` : ctr.name}
                          </option>
                        )
                      })}
                  </select>
                )}
              </div>
              <div className="form-actions">
                <button type="submit" className="btn btn-primary" disabled={updateCtrMutation.isPending}>
                  {updateCtrMutation.isPending ? 'Saving…' : 'Save'}
                </button>
                <button type="button" className="btn btn-secondary" onClick={() => setEditingCtr(null)}>
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
