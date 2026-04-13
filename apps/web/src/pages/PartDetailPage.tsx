import { useParams, Link, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { partsApi, stockApi, documentsApi, type Part, type StockItem, type PartDocumentLink } from '../api/client'
import { DOCUMENT_TYPES, PART_DOC_RELATIONSHIPS, formatBytes } from '../utils/documents'

export function PartDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [editing, setEditing] = useState(false)
  const [form, setForm] = useState<Partial<Part>>({})
  const [error, setError] = useState('')
  const [showDocUpload, setShowDocUpload] = useState(false)
  const [docFile, setDocFile] = useState<File | null>(null)
  const [docForm, setDocForm] = useState({ title: '', document_type: 'datasheet', relationship_type: 'primary_datasheet', is_primary: false, notes: '' })
  const [docUploadError, setDocUploadError] = useState('')

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

  const { data: partDocs, refetch: refetchDocs } = useQuery({
    queryKey: ['part-docs', id],
    queryFn: () => documentsApi.listForPart(id!),
    enabled: !!id,
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
    </div>
  )
}
