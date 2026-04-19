import { useParams, Link, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { partsApi, stockApi, documentsApi, locationsApi, containersApi, intakeApi, type Part, type StockItem, type PartDocumentLink, type PartAlias, type Location, type Container, type IntakeCandidate } from '../api/client'
import { DOCUMENT_TYPES, PART_DOC_RELATIONSHIPS, formatBytes } from '../utils/documents'
import { EnrichmentPanel } from '../components/EnrichmentPanel'

function DetailSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: '1.25rem' }}>
      <div style={{ fontSize: '0.7rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: '#9ca3af', marginBottom: '0.5rem' }}>
        {title}
      </div>
      {children}
    </div>
  )
}

function DetailRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', gap: '1.5rem', marginBottom: '0.3rem', fontSize: '0.9rem' }}>
      <span style={{ minWidth: '120px', color: '#6b7280', flexShrink: 0 }}>{label}</span>
      <span>{children}</span>
    </div>
  )
}

const STOCK_DEFAULT = {
  quantity: '',
  unit: '',
  supplier: '',
  notes: '',
  placementType: 'location' as 'location' | 'container',
  location_id: '',
  container_id: '',
  status: 'available',
}

export function PartDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [editing, setEditing] = useState(false)
  const [form, setForm] = useState<Partial<Part> & { part_code?: string }>({})
  const [error, setError] = useState('')
  const [showDocUpload, setShowDocUpload] = useState(false)
  const [docFile, setDocFile] = useState<File | null>(null)
  const [docForm, setDocForm] = useState({ title: '', document_type: 'datasheet', relationship_type: 'primary_datasheet', is_primary: false, notes: '' })
  const [docUploadError, setDocUploadError] = useState('')
  const [newAlias, setNewAlias] = useState('')
  const [aliasError, setAliasError] = useState('')

  // Part code suggestion state
  const [suggestingCode, setSuggestingCode] = useState(false)
  const [codeWarning, setCodeWarning] = useState<IntakeCandidate[] | null>(null)

  // Stock management state
  const [showAddStock, setShowAddStock] = useState(false)
  const [stockForm, setStockForm] = useState(STOCK_DEFAULT)
  const [stockError, setStockError] = useState('')
  const [editingStockId, setEditingStockId] = useState<string | null>(null)
  const [editStockForm, setEditStockForm] = useState<Partial<typeof STOCK_DEFAULT & { id: string }>>({})

  const { data: part, isLoading } = useQuery({
    queryKey: ['parts', id],
    queryFn: () => partsApi.get(id!),
    enabled: !!id,
  })

  const { data: stockData, refetch: refetchStock } = useQuery({
    queryKey: ['stock', 'part', id],
    queryFn: () => stockApi.list({ part_id: id!, limit: 50 }),
    enabled: !!id,
  })

  const { data: partDocs, refetch: refetchDocs } = useQuery({
    queryKey: ['part-docs', id],
    queryFn: () => documentsApi.listForPart(id!),
    enabled: !!id,
  })

  const { data: aliases, refetch: refetchAliases } = useQuery({
    queryKey: ['part-aliases', id],
    queryFn: () => partsApi.listAliases(id!),
    enabled: !!id,
  })

  const { data: locsData } = useQuery({
    queryKey: ['locations', 'list'],
    queryFn: () => locationsApi.list({ limit: 100 }),
    staleTime: 60_000,
  })

  const { data: ctrsData } = useQuery({
    queryKey: ['containers', 'list'],
    queryFn: () => containersApi.list({ limit: 200 }),
    staleTime: 60_000,
  })

  const addAliasMutation = useMutation({
    mutationFn: (alias: string) => partsApi.addAlias(id!, { alias }),
    onSuccess: () => {
      refetchAliases()
      qc.invalidateQueries({ queryKey: ['parts', id] })
      setNewAlias('')
      setAliasError('')
    },
    onError: (err: any) => {
      setAliasError(err?.response?.data?.detail ?? 'Failed to add alias')
    },
  })

  const removeAliasMutation = useMutation({
    mutationFn: (aliasId: string) => partsApi.removeAlias(id!, aliasId),
    onSuccess: () => {
      refetchAliases()
      qc.invalidateQueries({ queryKey: ['parts', id] })
    },
  })

  const unlinkDocMutation = useMutation({
    mutationFn: (linkId: string) => documentsApi.unlinkFromPart(id!, linkId),
    onSuccess: () => refetchDocs(),
  })

  const uploadAndLinkMutation = useMutation({
    mutationFn: async (fd: FormData) => {
      const doc = await documentsApi.upload(fd)
      return documentsApi.linkToPart(id!, {
        document_id: doc.id,
        relationship_type: docForm.relationship_type,
        is_primary: docForm.is_primary,
        notes: docForm.notes || undefined,
      })
    },
    onSuccess: () => {
      refetchDocs()
      setShowDocUpload(false)
      setDocFile(null)
      setDocForm({ title: '', document_type: 'datasheet', relationship_type: 'primary_datasheet', is_primary: false, notes: '' })
      setDocUploadError('')
    },
    onError: (err: any) => {
      setDocUploadError(err?.response?.data?.detail ?? 'Upload failed')
    },
  })

  const handleDocUpload = (e: React.FormEvent) => {
    e.preventDefault()
    if (!docFile) { setDocUploadError('Please select a file.'); return }
    const fd = new FormData()
    fd.append('file', docFile)
    fd.append('title', docForm.title || docFile.name)
    fd.append('document_type', docForm.document_type)
    uploadAndLinkMutation.mutate(fd)
  }

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

  // Stock mutations
  const createStockMutation = useMutation({
    mutationFn: (payload: Partial<StockItem>) => stockApi.create(payload),
    onSuccess: () => {
      refetchStock()
      qc.invalidateQueries({ queryKey: ['stock'] })
      setShowAddStock(false)
      setStockForm(STOCK_DEFAULT)
      setStockError('')
    },
    onError: (err: any) => {
      setStockError(err?.response?.data?.detail ?? 'Failed to add stock')
    },
  })

  const updateStockMutation = useMutation({
    mutationFn: ({ sid, payload }: { sid: string; payload: Partial<StockItem> }) =>
      stockApi.update(sid, payload),
    onSuccess: () => {
      refetchStock()
      qc.invalidateQueries({ queryKey: ['stock'] })
      setEditingStockId(null)
      setStockError('')
    },
    onError: (err: any) => {
      setStockError(err?.response?.data?.detail ?? 'Failed to update stock')
    },
  })

  const deleteStockMutation = useMutation({
    mutationFn: (sid: string) => stockApi.delete(sid),
    onSuccess: () => {
      refetchStock()
      qc.invalidateQueries({ queryKey: ['stock'] })
    },
    onError: (err: any) => alert(err?.response?.data?.detail ?? 'Failed to delete stock item'),
  })

  const handleSuggestCode = async () => {
    const desc = [form.name ?? part?.name, form.short_description].filter(Boolean).join(' ').trim()
    if (!desc) return
    setSuggestingCode(true)
    setCodeWarning(null)
    try {
      const result = await intakeApi.match(desc)
      setForm(f => ({ ...f, part_code: result.suggested_part_code }))
      // Exclude the current part itself from warnings
      const highConf = result.candidates.filter(c => c.confidence >= 50 && c.part_id !== id)
      if (highConf.length > 0) setCodeWarning(highConf)
    } catch {
      // ignore — user can still type
    } finally {
      setSuggestingCode(false)
    }
  }

  if (isLoading) return <div className="loading">Loading…</div>
  if (!part) return <div className="empty">Part not found.</div>

  const handleEdit = () => {
    setForm({
      part_code: part.part_code,
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

  const handleAddStock = (e: React.FormEvent) => {
    e.preventDefault()
    if (!stockForm.quantity) { setStockError('Quantity is required.'); return }
    const payload: Partial<StockItem> = {
      part_id: id!,
      quantity: parseFloat(stockForm.quantity),
      status: stockForm.status,
    }
    if (stockForm.unit) payload.unit = stockForm.unit
    if (stockForm.supplier) payload.supplier = stockForm.supplier
    if (stockForm.notes) payload.notes = stockForm.notes
    if (stockForm.placementType === 'location' && stockForm.location_id) {
      payload.location_id = stockForm.location_id
    } else if (stockForm.placementType === 'container' && stockForm.container_id) {
      payload.container_id = stockForm.container_id
    }
    createStockMutation.mutate(payload)
  }

  const handleEditStockOpen = (item: StockItem) => {
    setEditStockForm({
      quantity: String(item.quantity),
      unit: item.unit ?? '',
      supplier: item.supplier ?? '',
      notes: item.notes ?? '',
      placementType: item.container_id ? 'container' : 'location',
      location_id: item.location_id ?? '',
      container_id: item.container_id ?? '',
      status: item.status,
    })
    setEditingStockId(item.id)
    setStockError('')
  }

  const handleEditStockSubmit = (e: React.FormEvent, sid: string) => {
    e.preventDefault()
    const payload: Partial<StockItem> = {
      quantity: parseFloat(editStockForm.quantity ?? '0'),
      status: editStockForm.status,
    }
    payload.unit = editStockForm.unit || null
    payload.supplier = editStockForm.supplier || null
    payload.notes = editStockForm.notes || null
    if ((editStockForm.placementType as string) === 'location') {
      payload.location_id = editStockForm.location_id || null
      payload.container_id = null
    } else {
      payload.container_id = editStockForm.container_id || null
      payload.location_id = null
    }
    updateStockMutation.mutate({ sid, payload })
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
              <input className="form-control" value={form.name ?? ''} onChange={e => { setForm(f => ({ ...f, name: e.target.value })); setCodeWarning(null) }} />
            </div>
            <div className="form-group">
              <label className="form-label">Part Code</label>
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <input
                  className="form-control"
                  value={form.part_code ?? ''}
                  onChange={e => { setForm(f => ({ ...f, part_code: e.target.value })); setCodeWarning(null) }}
                />
                <button
                  type="button"
                  className="btn btn-secondary"
                  style={{ whiteSpace: 'nowrap', flexShrink: 0 }}
                  disabled={suggestingCode || !(form.name ?? part.name).trim()}
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
                    These may be duplicates — you can still save, but consider checking the{' '}
                    <a href="/intake" style={{ color: '#d97706', fontWeight: 600 }}>Intake page</a>
                    {' '}first.
                  </span>
                </div>
              )}
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
              <button type="button" className="btn btn-secondary" onClick={() => { setEditing(false); setCodeWarning(null) }}>Cancel</button>
            </div>
          </form>
        </div>
      ) : (
        <div className="card">
          {/* Core identity */}
          <DetailSection title="Identity">
            <DetailRow label="Status"><span className={`badge badge-${part.status}`}>{part.status}</span></DetailRow>
            <DetailRow label="Description">{part.short_description ?? '—'}</DetailRow>
            <DetailRow label="Manufacturer">{part.manufacturer ?? '—'}</DetailRow>
            <DetailRow label="MPN">{part.manufacturer_part_number ?? '—'}</DetailRow>
            <DetailRow label="Package">{part.package_type ?? '—'}</DetailRow>
            <DetailRow label="Default Unit">{part.default_unit}</DetailRow>
            <DetailRow label="Notes">{part.notes ?? '—'}</DetailRow>
          </DetailSection>

          {/* Taxonomy */}
          {(part.category || part.subcategory || part.family || part.form_factor) && (
            <DetailSection title="Classification">
              {part.category && <DetailRow label="Category"><code>{part.category}{part.subcategory ? `-${part.subcategory}` : ''}</code></DetailRow>}
              {part.family && <DetailRow label="Family">{part.family}</DetailRow>}
              {part.form_factor && <DetailRow label="Form Factor">{part.form_factor}</DetailRow>}
              {part.part_kind && <DetailRow label="Kind">{part.part_kind}</DetailRow>}
            </DetailSection>
          )}

          {/* Electrical */}
          {(part.interface?.length || part.voltage || part.logic_level) && (
            <DetailSection title="Electrical">
              {part.interface && part.interface.length > 0 && (
                <DetailRow label="Interface">{part.interface.join(', ')}</DetailRow>
              )}
              {part.voltage && <DetailRow label="Voltage">{part.voltage}</DetailRow>}
              {part.logic_level && <DetailRow label="Logic Level">{part.logic_level}</DetailRow>}
            </DetailSection>
          )}

          {/* Pinout */}
          {part.pins && part.pins.length > 0 && (
            <DetailSection title="Pinout">
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.3rem' }}>
                {part.pins.map((pin, i) => (
                  <span key={i} style={{ background: '#f3f4f6', border: '1px solid #e5e7eb', borderRadius: '4px', padding: '0.15rem 0.5rem', fontSize: '0.8rem', fontFamily: 'monospace' }}>
                    {pin}
                  </span>
                ))}
              </div>
            </DetailSection>
          )}

          {/* Capabilities */}
          {(part.capabilities?.length || part.use_cases?.length) && (
            <DetailSection title="Capabilities & Use Cases">
              {part.capabilities && part.capabilities.length > 0 && (
                <DetailRow label="What it does">
                  <ul style={{ margin: 0, paddingLeft: '1.2rem' }}>
                    {part.capabilities.map((c, i) => <li key={i}>{c}</li>)}
                  </ul>
                </DetailRow>
              )}
              {part.use_cases && part.use_cases.length > 0 && (
                <DetailRow label="Use cases">
                  <ul style={{ margin: 0, paddingLeft: '1.2rem' }}>
                    {part.use_cases.map((u, i) => <li key={i}>{u}</li>)}
                  </ul>
                </DetailRow>
              )}
            </DetailSection>
          )}

          {/* Key specs */}
          {part.key_specs && Object.keys(part.key_specs).length > 0 && (
            <DetailSection title="Key Specs">
              <table style={{ fontSize: '0.85rem' }}>
                <tbody>
                  {Object.entries(part.key_specs).map(([k, v]) => (
                    <tr key={k}>
                      <td style={{ color: '#6b7280', paddingRight: '1.5rem', whiteSpace: 'nowrap' }}>{k}</td>
                      <td>{String(v)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </DetailSection>
          )}

          {/* Flags */}
          {(part.protection_features?.length || part.special_flags?.length) && (
            <DetailSection title="Flags">
              {part.protection_features && part.protection_features.length > 0 && (
                <DetailRow label="Protection">{part.protection_features.join(', ')}</DetailRow>
              )}
              {part.special_flags && part.special_flags.length > 0 && (
                <DetailRow label="Special">{part.special_flags.join(', ')}</DetailRow>
              )}
            </DetailSection>
          )}

          {/* Tags */}
          {part.tags && part.tags.length > 0 && (
            <DetailSection title="Tags">
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
                {part.tags.map(tag => (
                  <span key={tag} className="badge badge-draft" style={{ fontSize: '0.8rem' }}>{tag}</span>
                ))}
              </div>
            </DetailSection>
          )}
        </div>
      )}

      {/* Stock items for this part */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginTop: '2rem', marginBottom: '1rem' }}>
        <h2 style={{ fontSize: '1.1rem', fontWeight: 600, margin: 0 }}>
          Stock ({stockData?.total ?? 0} item{stockData?.total !== 1 ? 's' : ''})
        </h2>
        <button className="btn btn-secondary btn-sm" onClick={() => { setStockError(''); setShowAddStock(true) }}>
          + Add Stock
        </button>
      </div>

      {stockError && <div className="alert alert-error" style={{ marginBottom: '0.75rem' }}>{stockError}</div>}

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
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {stockData.items.map((item: StockItem) => (
                editingStockId === item.id ? (
                  <tr key={item.id}>
                    <td colSpan={6} style={{ padding: '0.75rem' }}>
                      <form onSubmit={e => handleEditStockSubmit(e, item.id)} style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', alignItems: 'flex-end' }}>
                        <div>
                          <label style={{ fontSize: '0.75rem', color: '#6b7280', display: 'block' }}>Qty *</label>
                          <input
                            className="form-control"
                            style={{ width: '80px' }}
                            type="number"
                            step="any"
                            required
                            value={editStockForm.quantity ?? ''}
                            onChange={e => setEditStockForm(f => ({ ...f, quantity: e.target.value }))}
                          />
                        </div>
                        <div>
                          <label style={{ fontSize: '0.75rem', color: '#6b7280', display: 'block' }}>Unit</label>
                          <input
                            className="form-control"
                            style={{ width: '70px' }}
                            value={editStockForm.unit ?? ''}
                            onChange={e => setEditStockForm(f => ({ ...f, unit: e.target.value }))}
                            placeholder={part.default_unit}
                          />
                        </div>
                        <div>
                          <label style={{ fontSize: '0.75rem', color: '#6b7280', display: 'block' }}>Status</label>
                          <select
                            className="form-control"
                            style={{ width: '110px' }}
                            value={editStockForm.status ?? 'available'}
                            onChange={e => setEditStockForm(f => ({ ...f, status: e.target.value }))}
                          >
                            <option value="available">Available</option>
                            <option value="reserved">Reserved</option>
                            <option value="used">Used</option>
                            <option value="damaged">Damaged</option>
                          </select>
                        </div>
                        <div>
                          <label style={{ fontSize: '0.75rem', color: '#6b7280', display: 'block' }}>Placement</label>
                          <select
                            className="form-control"
                            style={{ width: '110px' }}
                            value={editStockForm.placementType ?? 'location'}
                            onChange={e => setEditStockForm(f => ({ ...f, placementType: e.target.value as 'location' | 'container' }))}
                          >
                            <option value="location">Location</option>
                            <option value="container">Container</option>
                          </select>
                        </div>
                        {editStockForm.placementType === 'location' ? (
                          <div>
                            <label style={{ fontSize: '0.75rem', color: '#6b7280', display: 'block' }}>Location</label>
                            <select
                              className="form-control"
                              style={{ width: '140px' }}
                              value={editStockForm.location_id ?? ''}
                              onChange={e => setEditStockForm(f => ({ ...f, location_id: e.target.value }))}
                            >
                              <option value="">— none —</option>
                              {locsData?.items.map((l: Location) => (
                                <option key={l.id} value={l.id}>{l.name}</option>
                              ))}
                            </select>
                          </div>
                        ) : (
                          <div>
                            <label style={{ fontSize: '0.75rem', color: '#6b7280', display: 'block' }}>Container</label>
                            <select
                              className="form-control"
                              style={{ width: '140px' }}
                              value={editStockForm.container_id ?? ''}
                              onChange={e => setEditStockForm(f => ({ ...f, container_id: e.target.value }))}
                            >
                              <option value="">— none —</option>
                              {ctrsData?.items.map((c: Container) => (
                                <option key={c.id} value={c.id}>{c.name}</option>
                              ))}
                            </select>
                          </div>
                        )}
                        <div>
                          <label style={{ fontSize: '0.75rem', color: '#6b7280', display: 'block' }}>Supplier</label>
                          <input
                            className="form-control"
                            style={{ width: '120px' }}
                            value={editStockForm.supplier ?? ''}
                            onChange={e => setEditStockForm(f => ({ ...f, supplier: e.target.value }))}
                          />
                        </div>
                        <div style={{ display: 'flex', gap: '0.4rem' }}>
                          <button type="submit" className="btn btn-primary btn-sm" disabled={updateStockMutation.isPending}>
                            {updateStockMutation.isPending ? '…' : 'Save'}
                          </button>
                          <button type="button" className="btn btn-secondary btn-sm" onClick={() => setEditingStockId(null)}>
                            Cancel
                          </button>
                        </div>
                      </form>
                    </td>
                  </tr>
                ) : (
                  <tr key={item.id}>
                    <td style={{ fontWeight: 500 }}>{item.quantity}</td>
                    <td>{item.unit ?? part.default_unit}</td>
                    <td><span className={`badge badge-${item.status}`}>{item.status}</span></td>
                    <td>
                      {item.container_name
                        ? item.container_name
                        : item.location_name
                        ? item.location_name
                        : item.container_id
                        ? `ctr:${item.container_id.slice(0, 8)}…`
                        : item.location_id
                        ? `loc:${item.location_id.slice(0, 8)}…`
                        : '—'}
                    </td>
                    <td>{item.supplier ?? '—'}</td>
                    <td style={{ whiteSpace: 'nowrap' }}>
                      <button
                        className="btn btn-secondary btn-sm"
                        style={{ marginRight: '0.3rem' }}
                        onClick={() => handleEditStockOpen(item)}
                      >
                        Edit
                      </button>
                      <button
                        className="btn btn-danger btn-sm"
                        onClick={() => { if (confirm('Delete this stock item?')) deleteStockMutation.mutate(item.id) }}
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                )
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Add Stock modal */}
      {showAddStock && (
        <div className="modal-overlay" onClick={() => setShowAddStock(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-title">Add Stock</div>
            {stockError && <div className="alert alert-error">{stockError}</div>}
            <form onSubmit={handleAddStock}>
              <div className="form-group">
                <label className="form-label">Quantity *</label>
                <input
                  className="form-control"
                  type="number"
                  step="any"
                  required
                  value={stockForm.quantity}
                  onChange={e => setStockForm(f => ({ ...f, quantity: e.target.value }))}
                  placeholder="e.g. 10"
                />
              </div>
              <div className="form-group">
                <label className="form-label">Unit</label>
                <input
                  className="form-control"
                  value={stockForm.unit}
                  onChange={e => setStockForm(f => ({ ...f, unit: e.target.value }))}
                  placeholder={part.default_unit}
                />
              </div>
              <div className="form-group">
                <label className="form-label">Status</label>
                <select
                  className="form-control"
                  value={stockForm.status}
                  onChange={e => setStockForm(f => ({ ...f, status: e.target.value }))}
                >
                  <option value="available">Available</option>
                  <option value="reserved">Reserved</option>
                  <option value="used">Used</option>
                  <option value="damaged">Damaged</option>
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Stored in</label>
                <div style={{ display: 'flex', gap: '1rem', marginBottom: '0.5rem' }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', cursor: 'pointer', fontSize: '0.875rem' }}>
                    <input
                      type="radio"
                      name="stockPlacement"
                      value="location"
                      checked={stockForm.placementType === 'location'}
                      onChange={() => setStockForm(f => ({ ...f, placementType: 'location', container_id: '' }))}
                    />
                    Location
                  </label>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', cursor: 'pointer', fontSize: '0.875rem' }}>
                    <input
                      type="radio"
                      name="stockPlacement"
                      value="container"
                      checked={stockForm.placementType === 'container'}
                      onChange={() => setStockForm(f => ({ ...f, placementType: 'container', location_id: '' }))}
                    />
                    Container
                  </label>
                </div>
                {stockForm.placementType === 'location' ? (
                  <select
                    className="form-control"
                    value={stockForm.location_id}
                    onChange={e => setStockForm(f => ({ ...f, location_id: e.target.value }))}
                  >
                    <option value="">— no location —</option>
                    {locsData?.items.map((l: Location) => (
                      <option key={l.id} value={l.id}>{l.name}</option>
                    ))}
                  </select>
                ) : (
                  <select
                    className="form-control"
                    value={stockForm.container_id}
                    onChange={e => setStockForm(f => ({ ...f, container_id: e.target.value }))}
                  >
                    <option value="">— no container —</option>
                    {ctrsData?.items.map((c: Container) => (
                      <option key={c.id} value={c.id}>{c.name}</option>
                    ))}
                  </select>
                )}
              </div>
              <div className="form-group">
                <label className="form-label">Supplier</label>
                <input
                  className="form-control"
                  value={stockForm.supplier}
                  onChange={e => setStockForm(f => ({ ...f, supplier: e.target.value }))}
                  placeholder="e.g. Mouser, Farnell"
                />
              </div>
              <div className="form-group">
                <label className="form-label">Notes</label>
                <textarea
                  className="form-control"
                  rows={2}
                  value={stockForm.notes}
                  onChange={e => setStockForm(f => ({ ...f, notes: e.target.value }))}
                />
              </div>
              <div className="form-actions">
                <button type="submit" className="btn btn-primary" disabled={createStockMutation.isPending}>
                  {createStockMutation.isPending ? 'Adding…' : 'Add Stock'}
                </button>
                <button type="button" className="btn btn-secondary" onClick={() => { setShowAddStock(false); setStockError('') }}>
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginTop: '2rem', marginBottom: '1rem' }}>
        <h2 style={{ fontSize: '1.1rem', fontWeight: 600, margin: 0 }}>
          Aliases ({aliases?.length ?? 0})
        </h2>
      </div>
      {aliasError && <div className="alert alert-error" style={{ marginBottom: '0.75rem' }}>{aliasError}</div>}
      <form
        onSubmit={e => { e.preventDefault(); if (newAlias.trim()) addAliasMutation.mutate(newAlias.trim()) }}
        style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem' }}
      >
        <input
          className="form-control"
          placeholder="Add alias (e.g. ESP-WROOM-32)"
          value={newAlias}
          onChange={e => setNewAlias(e.target.value)}
          style={{ maxWidth: '300px' }}
        />
        <button type="submit" className="btn btn-secondary btn-sm" disabled={addAliasMutation.isPending || !newAlias.trim()}>
          {addAliasMutation.isPending ? 'Adding…' : '+ Add'}
        </button>
      </form>
      {!aliases || aliases.length === 0 ? (
        <div className="empty" style={{ padding: '1rem 1.5rem' }}>No aliases. Aliases let you find this part by alternate names.</div>
      ) : (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem', marginBottom: '1rem' }}>
          {aliases.map((a: PartAlias) => (
            <span key={a.id} style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem', background: '#f3f4f6', border: '1px solid #e5e7eb', borderRadius: '4px', padding: '0.2rem 0.5rem', fontSize: '0.85rem' }}>
              {a.alias}
              <button
                onClick={() => { if (confirm(`Remove alias "${a.alias}"?`)) removeAliasMutation.mutate(a.id) }}
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#9ca3af', fontSize: '0.75rem', padding: 0, lineHeight: 1 }}
              >
                ✕
              </button>
            </span>
          ))}
        </div>
      )}

      {/* Documents for this part */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginTop: '2rem', marginBottom: '1rem' }}>
        <h2 style={{ fontSize: '1.1rem', fontWeight: 600, margin: 0 }}>
          Documents ({partDocs?.length ?? 0})
        </h2>
        <button className="btn btn-secondary btn-sm" onClick={() => setShowDocUpload(true)}>
          + Attach Document
        </button>
      </div>

      {showDocUpload && (
        <div className="modal-backdrop">
          <div className="modal">
            <div className="modal-header">
              <h2 className="modal-title">Attach Document</h2>
              <button className="modal-close" onClick={() => { setShowDocUpload(false); setDocUploadError('') }}>✕</button>
            </div>
            {docUploadError && <div className="alert alert-error">{docUploadError}</div>}
            <form onSubmit={handleDocUpload}>
              <div className="form-group">
                <label className="form-label">File *</label>
                <input type="file" className="form-control" onChange={e => setDocFile(e.target.files?.[0] ?? null)} />
              </div>
              <div className="form-group">
                <label className="form-label">Title</label>
                <input className="form-control" placeholder="Leave blank to use filename" value={docForm.title} onChange={e => setDocForm(f => ({ ...f, title: e.target.value }))} />
              </div>
              <div className="form-group">
                <label className="form-label">Document type</label>
                <select className="form-control" value={docForm.document_type} onChange={e => setDocForm(f => ({ ...f, document_type: e.target.value }))}>
                  {DOCUMENT_TYPES.map(t => <option key={t} value={t}>{t.replace(/_/g, ' ')}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Relationship</label>
                <select className="form-control" value={docForm.relationship_type} onChange={e => setDocForm(f => ({ ...f, relationship_type: e.target.value }))}>
                  {PART_DOC_RELATIONSHIPS.map(r => <option key={r} value={r}>{r.replace(/_/g, ' ')}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <input type="checkbox" checked={docForm.is_primary} onChange={e => setDocForm(f => ({ ...f, is_primary: e.target.checked }))} />
                  Primary document
                </label>
              </div>
              <div className="form-actions">
                <button type="submit" className="btn btn-primary" disabled={uploadAndLinkMutation.isPending}>
                  {uploadAndLinkMutation.isPending ? 'Uploading…' : 'Upload & Attach'}
                </button>
                <button type="button" className="btn btn-secondary" onClick={() => { setShowDocUpload(false); setDocUploadError('') }}>Cancel</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {!partDocs || partDocs.length === 0 ? (
        <div className="empty" style={{ padding: '1.5rem' }}>No documents attached to this part.</div>
      ) : (
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Title</th>
                <th>Type</th>
                <th>Relationship</th>
                <th>Size</th>
                <th>Checksum</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {partDocs.map((link: PartDocumentLink) => (
                <tr key={link.id}>
                  <td style={{ fontWeight: 500 }}>
                    {link.document.title}
                    {link.is_primary && (
                      <span style={{ marginLeft: '0.4rem', color: '#059669', fontSize: '0.75rem', fontWeight: 600 }}>★ primary</span>
                    )}
                  </td>
                  <td><span className="badge badge-draft">{link.document.document_type.replace(/_/g, ' ')}</span></td>
                  <td style={{ fontSize: '0.85rem', color: '#6b7280' }}>{link.relationship_type.replace(/_/g, ' ')}</td>
                  <td style={{ fontSize: '0.85rem' }}>{formatBytes(link.document.file_size_bytes)}</td>
                  <td style={{ fontFamily: 'monospace', fontSize: '0.75rem', color: '#6b7280' }}>
                    {link.document.checksum ? link.document.checksum.slice(0, 12) + '…' : '—'}
                  </td>
                  <td>
                    <button
                      className="btn btn-danger btn-sm"
                      onClick={() => { if (confirm('Remove this document link?')) unlinkDocMutation.mutate(link.id) }}
                    >
                      Remove
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* AI Enrichment */}
      <h2 style={{ fontSize: '1.1rem', fontWeight: 600, marginTop: '2rem', marginBottom: '1rem' }}>
        AI Enrichment
      </h2>
      <EnrichmentPanel
        entityType="part"
        entityId={id!}
        onApplied={() => {
          qc.invalidateQueries({ queryKey: ['parts', id] })
          qc.invalidateQueries({ queryKey: ['part-aliases', id] })
        }}
      />
    </div>
  )
}
