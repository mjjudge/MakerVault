import { useParams, Link, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { projectsApi, partsApi, documentsApi, type Project, type ProjectPart, type BOMEntryAvailability } from '../api/client'
import { DOCUMENT_TYPES } from '../utils/documents'

const STATUS_OPTIONS = ['active', 'on_hold', 'completed', 'archived']

export function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [editing, setEditing] = useState(false)
  const [form, setForm] = useState<Partial<Project>>({})
  const [error, setError] = useState('')

  // BOM state
  const [showAddPart, setShowAddPart] = useState(false)
  const [partSearch, setPartSearch] = useState('')
  const [bomForm, setBomForm] = useState({ part_id: '', quantity_required: 1, unit: '', notes: '' })
  const [bomError, setBomError] = useState('')

  // Document state
  const [showDocUpload, setShowDocUpload] = useState(false)
  const [docFile, setDocFile] = useState<File | null>(null)
  const [docForm, setDocForm] = useState({ title: '', document_type: 'other', relationship_type: 'other', notes: '' })
  const [docUploadError, setDocUploadError] = useState('')

  const { data: project, isLoading } = useQuery({
    queryKey: ['projects', id],
    queryFn: () => projectsApi.get(id!),
    enabled: !!id,
  })

  const { data: bomEntries, refetch: refetchBOM } = useQuery({
    queryKey: ['projects', id, 'parts'],
    queryFn: () => projectsApi.listParts(id!),
    enabled: !!id,
  })

  const { data: availability, refetch: refetchAvailability } = useQuery({
    queryKey: ['projects', id, 'availability'],
    queryFn: () => projectsApi.getAvailability(id!),
    enabled: !!id,
  })

  const { data: projectDocs, refetch: refetchDocs } = useQuery({
    queryKey: ['project-docs', id],
    queryFn: () => documentsApi.listForProject(id!),
    enabled: !!id,
  })

  // Part search for BOM add dialog
  const { data: partResults } = useQuery({
    queryKey: ['parts', 'bom-search', partSearch],
    queryFn: () => partsApi.list({ q: partSearch || undefined, limit: 20 }),
    enabled: partSearch.length >= 2,
  })

  const updateMutation = useMutation({
    mutationFn: (payload: Partial<Project>) => projectsApi.update(id!, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['projects', id] })
      qc.invalidateQueries({ queryKey: ['projects', 'list'] })
      setEditing(false)
      setError('')
    },
    onError: (err: any) => { setError(err?.response?.data?.detail ?? 'Update failed') },
  })

  const deleteMutation = useMutation({
    mutationFn: () => projectsApi.delete(id!),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['projects'] })
      navigate('/projects')
    },
  })

  const addPartMutation = useMutation({
    mutationFn: () => projectsApi.addPart(id!, {
      part_id: bomForm.part_id,
      quantity_required: bomForm.quantity_required,
      unit: bomForm.unit || undefined,
      notes: bomForm.notes || undefined,
    }),
    onSuccess: () => {
      refetchBOM()
      refetchAvailability()
      setShowAddPart(false)
      setBomForm({ part_id: '', quantity_required: 1, unit: '', notes: '' })
      setPartSearch('')
      setBomError('')
    },
    onError: (err: any) => { setBomError(err?.response?.data?.detail ?? 'Failed to add part') },
  })

  const removePartMutation = useMutation({
    mutationFn: (entryId: string) => projectsApi.removePart(id!, entryId),
    onSuccess: () => { refetchBOM(); refetchAvailability() },
  })

  const unlinkDocMutation = useMutation({
    mutationFn: (linkId: string) => documentsApi.unlinkFromProject(id!, linkId),
    onSuccess: () => refetchDocs(),
  })

  const uploadAndLinkDocMutation = useMutation({
    mutationFn: async (fd: FormData) => {
      const doc = await documentsApi.upload(fd)
      return documentsApi.linkToProject(id!, {
        document_id: doc.id,
        relationship_type: docForm.relationship_type,
        notes: docForm.notes || undefined,
      })
    },
    onSuccess: () => {
      refetchDocs()
      setShowDocUpload(false)
      setDocFile(null)
      setDocForm({ title: '', document_type: 'other', relationship_type: 'other', notes: '' })
      setDocUploadError('')
    },
    onError: (err: any) => { setDocUploadError(err?.response?.data?.detail ?? 'Upload failed') },
  })

  if (isLoading) return <div className="loading">Loading…</div>
  if (!project) return <div className="empty">Project not found.</div>

  const handleEdit = () => {
    setForm({ name: project.name, description: project.description ?? '', status: project.status, notes: project.notes ?? '' })
    setEditing(true)
  }

  const handleUpdate = (e: React.FormEvent) => {
    e.preventDefault()
    const payload: Partial<Project> = {}
    for (const [k, v] of Object.entries(form)) {
      if (v !== '') (payload as any)[k] = v
    }
    updateMutation.mutate(payload)
  }

  const handleAddPart = (e: React.FormEvent) => {
    e.preventDefault()
    if (!bomForm.part_id) { setBomError('Please select a part.'); return }
    addPartMutation.mutate()
  }

  const handleDocUpload = (e: React.FormEvent) => {
    e.preventDefault()
    if (!docFile) { setDocUploadError('Please select a file.'); return }
    const fd = new FormData()
    fd.append('file', docFile)
    fd.append('title', docForm.title || docFile.name)
    fd.append('document_type', docForm.document_type)
    uploadAndLinkDocMutation.mutate(fd)
  }

  // Availability map for quick lookup
  const availMap: Record<string, BOMEntryAvailability> = {}
  if (availability?.entries) {
    for (const e of availability.entries) availMap[e.project_part_id] = e
  }

  return (
    <div>
      <div style={{ marginBottom: '1rem' }}>
        <Link to="/projects" style={{ color: '#6b7280', fontSize: '0.875rem' }}>← Projects</Link>
      </div>

      <div className="page-header">
        <div>
          <h1 className="page-title">{project.name}</h1>
          <span style={{ color: '#6b7280', fontSize: '0.9rem' }}>
            <span className={`badge badge-${project.status === 'active' ? 'active' : project.status === 'completed' ? 'active' : 'draft'}`}>
              {project.status.replace(/_/g, ' ')}
            </span>
          </span>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button className="btn btn-secondary btn-sm" onClick={handleEdit}>Edit</button>
          <button
            className="btn btn-danger btn-sm"
            onClick={() => { if (confirm('Delete this project and all its BOM entries?')) deleteMutation.mutate() }}
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
              <label className="form-label">Description</label>
              <textarea className="form-control" rows={2} value={form.description ?? ''} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} />
            </div>
            <div className="form-group">
              <label className="form-label">Status</label>
              <select className="form-control" value={form.status ?? 'active'} onChange={e => setForm(f => ({ ...f, status: e.target.value }))}>
                {STATUS_OPTIONS.map(s => <option key={s} value={s}>{s.replace(/_/g, ' ')}</option>)}
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
                ['Description', project.description ?? '—'],
                ['Notes', project.notes ?? '—'],
                ['Created', new Date(project.created_at).toLocaleString()],
                ['Updated', new Date(project.updated_at).toLocaleString()],
              ].map(([label, value]) => (
                <tr key={label as string}>
                  <td style={{ fontWeight: 500, paddingRight: '2rem', color: '#6b7280', whiteSpace: 'nowrap', verticalAlign: 'top' }}>{label}</td>
                  <td>{value}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* BOM Availability Summary */}
      {availability && bomEntries && bomEntries.length > 0 && (
        <div className="card" style={{ marginTop: '2rem', padding: '1rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <span style={{ fontWeight: 600, fontSize: '0.95rem' }}>BOM Availability:</span>
            {availability.all_available ? (
              <span style={{ color: '#059669', fontWeight: 600 }}>✓ All parts available in stock</span>
            ) : (
              <span style={{ color: '#dc2626', fontWeight: 600 }}>⚠ Some parts are short or missing</span>
            )}
          </div>
        </div>
      )}

      {/* Bill of Materials */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginTop: '2rem', marginBottom: '1rem' }}>
        <h2 style={{ fontSize: '1.1rem', fontWeight: 600, margin: 0 }}>
          Bill of Materials ({bomEntries?.length ?? 0})
        </h2>
        <button className="btn btn-secondary btn-sm" onClick={() => setShowAddPart(true)}>
          + Add Part
        </button>
      </div>

      {showAddPart && (
        <div className="modal-overlay">
          <div className="modal">
            <div className="modal-header">
              <h2 className="modal-title">Add Part to BOM</h2>
              <button className="modal-close" onClick={() => { setShowAddPart(false); setBomError('') }}>✕</button>
            </div>
            {bomError && <div className="alert alert-error">{bomError}</div>}
            <form onSubmit={handleAddPart}>
              <div className="form-group">
                <label className="form-label">Search Part</label>
                <input
                  className="form-control"
                  placeholder="Type part name or code…"
                  value={partSearch}
                  onChange={e => setPartSearch(e.target.value)}
                />
                {partResults && partResults.items.length > 0 && !bomForm.part_id && (
                  <div style={{ border: '1px solid #e5e7eb', borderRadius: '0.375rem', marginTop: '0.25rem', maxHeight: '180px', overflowY: 'auto' }}>
                    {partResults.items.map(p => (
                      <div
                        key={p.id}
                        style={{ padding: '0.5rem 0.75rem', cursor: 'pointer' }}
                        onMouseOver={e => (e.currentTarget.style.background = '#f9fafb')}
                        onMouseOut={e => (e.currentTarget.style.background = '')}
                        onClick={() => {
                          setBomForm(f => ({ ...f, part_id: p.id }))
                          setPartSearch(`${p.part_code} — ${p.name}`)
                        }}
                      >
                        <span style={{ fontFamily: 'monospace', fontWeight: 500 }}>{p.part_code}</span>
                        {' — '}
                        {p.name}
                      </div>
                    ))}
                  </div>
                )}
                {bomForm.part_id && (
                  <div style={{ fontSize: '0.8rem', color: '#059669', marginTop: '0.25rem' }}>
                    ✓ Part selected
                    <button type="button" style={{ marginLeft: '0.5rem', color: '#6b7280', fontSize: '0.75rem', background: 'none', border: 'none', cursor: 'pointer' }}
                      onClick={() => { setBomForm(f => ({ ...f, part_id: '' })); setPartSearch('') }}>
                      Change
                    </button>
                  </div>
                )}
              </div>
              <div className="form-group">
                <label className="form-label">Quantity Required</label>
                <input
                  type="number"
                  className="form-control"
                  min="0.0001"
                  step="any"
                  value={bomForm.quantity_required}
                  onChange={e => setBomForm(f => ({ ...f, quantity_required: parseFloat(e.target.value) || 1 }))}
                />
              </div>
              <div className="form-group">
                <label className="form-label">Unit (optional)</label>
                <input
                  className="form-control"
                  placeholder="pcs, g, m…"
                  value={bomForm.unit}
                  onChange={e => setBomForm(f => ({ ...f, unit: e.target.value }))}
                />
              </div>
              <div className="form-group">
                <label className="form-label">Notes</label>
                <input
                  className="form-control"
                  value={bomForm.notes}
                  onChange={e => setBomForm(f => ({ ...f, notes: e.target.value }))}
                />
              </div>
              <div className="form-actions">
                <button type="submit" className="btn btn-primary" disabled={addPartMutation.isPending}>
                  {addPartMutation.isPending ? 'Adding…' : 'Add to BOM'}
                </button>
                <button type="button" className="btn btn-secondary" onClick={() => { setShowAddPart(false); setBomError('') }}>Cancel</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {!bomEntries || bomEntries.length === 0 ? (
        <div className="empty" style={{ padding: '1.5rem' }}>No parts in BOM yet. Add parts to track what you need.</div>
      ) : (
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Part</th>
                <th>Qty Required</th>
                <th>In Stock</th>
                <th>Available</th>
                <th>Notes</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {bomEntries.map((entry: ProjectPart) => {
                const avail = availMap[entry.id]
                return (
                  <tr key={entry.id}>
                    <td>
                      <Link to={`/parts/${entry.part_id}`} style={{ fontWeight: 500 }}>
                        {entry.part.name}
                      </Link>
                      <div style={{ fontFamily: 'monospace', fontSize: '0.75rem', color: '#6b7280' }}>{entry.part.part_code}</div>
                    </td>
                    <td style={{ fontWeight: 500 }}>
                      {entry.quantity_required}{entry.unit ? ` ${entry.unit}` : ''}
                    </td>
                    <td style={{ fontSize: '0.9rem' }}>
                      {avail ? avail.total_in_stock : '—'}
                    </td>
                    <td>
                      {avail ? (
                        avail.is_available
                          ? <span style={{ color: '#059669', fontWeight: 600 }}>✓</span>
                          : <span style={{ color: '#dc2626', fontWeight: 600 }}>✗</span>
                      ) : '—'}
                    </td>
                    <td style={{ fontSize: '0.85rem', color: '#6b7280' }}>{entry.notes ?? '—'}</td>
                    <td>
                      <button
                        className="btn btn-danger btn-sm"
                        onClick={() => { if (confirm('Remove from BOM?')) removePartMutation.mutate(entry.id) }}
                      >
                        Remove
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Documents */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginTop: '2rem', marginBottom: '1rem' }}>
        <h2 style={{ fontSize: '1.1rem', fontWeight: 600, margin: 0 }}>
          Documents ({projectDocs?.length ?? 0})
        </h2>
        <button className="btn btn-secondary btn-sm" onClick={() => setShowDocUpload(true)}>
          + Attach Document
        </button>
      </div>

      {showDocUpload && (
        <div className="modal-overlay">
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
                  {['wiring_note', 'photo', 'setup_instruction', 'design_sketch', 'ai_plan', 'reference', 'other'].map(r => (
                    <option key={r} value={r}>{r.replace(/_/g, ' ')}</option>
                  ))}
                </select>
              </div>
              <div className="form-actions">
                <button type="submit" className="btn btn-primary" disabled={uploadAndLinkDocMutation.isPending}>
                  {uploadAndLinkDocMutation.isPending ? 'Uploading…' : 'Upload & Attach'}
                </button>
                <button type="button" className="btn btn-secondary" onClick={() => { setShowDocUpload(false); setDocUploadError('') }}>Cancel</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {!projectDocs || projectDocs.length === 0 ? (
        <div className="empty" style={{ padding: '1.5rem' }}>No documents attached to this project.</div>
      ) : (
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Title</th>
                <th>Type</th>
                <th>Relationship</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {projectDocs.map((link: any) => (
                <tr key={link.id}>
                  <td style={{ fontWeight: 500 }}>{link.document.title}</td>
                  <td><span className="badge badge-draft">{link.document.document_type.replace(/_/g, ' ')}</span></td>
                  <td style={{ fontSize: '0.85rem', color: '#6b7280' }}>{link.relationship_type.replace(/_/g, ' ')}</td>
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
    </div>
  )
}
