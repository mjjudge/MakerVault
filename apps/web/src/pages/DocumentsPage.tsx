import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { documentsApi, type Document } from '../api/client'
import { DOCUMENT_TYPES, formatBytes } from '../utils/documents'

export function DocumentsPage() {
  const qc = useQueryClient()
  const [q, setQ] = useState('')
  const [typeFilter, setTypeFilter] = useState('')
  const [showUpload, setShowUpload] = useState(false)
  const [uploadForm, setUploadForm] = useState({
    title: '',
    document_type: 'other',
    source_url: '',
    notes: '',
  })
  const [file, setFile] = useState<File | null>(null)
  const [uploadError, setUploadError] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: ['documents', q, typeFilter],
    queryFn: () =>
      documentsApi.list({
        q: q || undefined,
        document_type: typeFilter || undefined,
        limit: 100,
      }),
  })

  const uploadMutation = useMutation({
    mutationFn: (fd: FormData) => documentsApi.upload(fd),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['documents'] })
      setShowUpload(false)
      setUploadForm({ title: '', document_type: 'other', source_url: '', notes: '' })
      setFile(null)
      setUploadError('')
    },
    onError: (err: any) => {
      setUploadError(err?.response?.data?.detail ?? 'Upload failed')
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => documentsApi.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['documents'] }),
  })

  const handleUpload = (e: React.FormEvent) => {
    e.preventDefault()
    if (!file) {
      setUploadError('Please select a file to upload.')
      return
    }
    const fd = new FormData()
    fd.append('file', file)
    fd.append('title', uploadForm.title || file.name)
    fd.append('document_type', uploadForm.document_type)
    if (uploadForm.source_url) fd.append('source_url', uploadForm.source_url)
    if (uploadForm.notes) fd.append('notes', uploadForm.notes)
    uploadMutation.mutate(fd)
  }

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Documents</h1>
        <button className="btn btn-primary btn-sm" onClick={() => setShowUpload(true)}>
          + Upload Document
        </button>
      </div>

      {/* Upload modal */}
      {showUpload && (
        <div className="modal-backdrop">
          <div className="modal">
            <div className="modal-header">
              <h2 className="modal-title">Upload Document</h2>
              <button className="modal-close" onClick={() => { setShowUpload(false); setUploadError('') }}>✕</button>
            </div>
            {uploadError && <div className="alert alert-error">{uploadError}</div>}
            <form onSubmit={handleUpload}>
              <div className="form-group">
                <label className="form-label">File *</label>
                <input
                  type="file"
                  className="form-control"
                  onChange={e => setFile(e.target.files?.[0] ?? null)}
                />
              </div>
              <div className="form-group">
                <label className="form-label">Title</label>
                <input
                  className="form-control"
                  placeholder="Leave blank to use filename"
                  value={uploadForm.title}
                  onChange={e => setUploadForm(f => ({ ...f, title: e.target.value }))}
                />
              </div>
              <div className="form-group">
                <label className="form-label">Type</label>
                <select
                  className="form-control"
                  value={uploadForm.document_type}
                  onChange={e => setUploadForm(f => ({ ...f, document_type: e.target.value }))}
                >
                  {DOCUMENT_TYPES.map(t => (
                    <option key={t} value={t}>{t.replace(/_/g, ' ')}</option>
                  ))}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Source URL</label>
                <input
                  className="form-control"
                  placeholder="https://…"
                  value={uploadForm.source_url}
                  onChange={e => setUploadForm(f => ({ ...f, source_url: e.target.value }))}
                />
              </div>
              <div className="form-group">
                <label className="form-label">Notes</label>
                <textarea
                  className="form-control"
                  rows={2}
                  value={uploadForm.notes}
                  onChange={e => setUploadForm(f => ({ ...f, notes: e.target.value }))}
                />
              </div>
              <div className="form-actions">
                <button type="submit" className="btn btn-primary" disabled={uploadMutation.isPending}>
                  {uploadMutation.isPending ? 'Uploading…' : 'Upload'}
                </button>
                <button type="button" className="btn btn-secondary" onClick={() => { setShowUpload(false); setUploadError('') }}>
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Filters */}
      <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '1.25rem', flexWrap: 'wrap' }}>
        <input
          className="form-control"
          style={{ maxWidth: 320 }}
          placeholder="Search by title…"
          value={q}
          onChange={e => setQ(e.target.value)}
        />
        <select
          className="form-control"
          style={{ maxWidth: 200 }}
          value={typeFilter}
          onChange={e => setTypeFilter(e.target.value)}
        >
          <option value="">All types</option>
          {DOCUMENT_TYPES.map(t => (
            <option key={t} value={t}>{t.replace(/_/g, ' ')}</option>
          ))}
        </select>
      </div>

      {isLoading && <div className="loading">Loading…</div>}
      {!isLoading && (!data || data.items.length === 0) && (
        <div className="empty">No documents found. Upload one to get started.</div>
      )}

      {data && data.items.length > 0 && (
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Title</th>
                <th>Type</th>
                <th>MIME</th>
                <th>Size</th>
                <th>Checksum (SHA-256)</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((doc: Document) => (
                <tr key={doc.id}>
                  <td style={{ fontWeight: 500 }}>
                    {doc.title}
                    {doc.version_label && (
                      <span style={{ marginLeft: '0.5rem', color: '#6b7280', fontSize: '0.8rem' }}>
                        ({doc.version_label})
                      </span>
                    )}
                  </td>
                  <td>
                    <span className="badge badge-draft">{doc.document_type.replace(/_/g, ' ')}</span>
                  </td>
                  <td style={{ fontFamily: 'monospace', fontSize: '0.8rem', color: '#6b7280' }}>
                    {doc.mime_type ?? '—'}
                  </td>
                  <td style={{ fontSize: '0.85rem' }}>{formatBytes(doc.file_size_bytes)}</td>
                  <td style={{ fontFamily: 'monospace', fontSize: '0.75rem', color: '#6b7280' }}>
                    {doc.checksum ? doc.checksum.slice(0, 12) + '…' : '—'}
                  </td>
                  <td>
                    <button
                      className="btn btn-danger btn-sm"
                      onClick={() => {
                        if (confirm(`Delete "${doc.title}"?`)) deleteMutation.mutate(doc.id)
                      }}
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div style={{ marginTop: '0.5rem', color: '#6b7280', fontSize: '0.85rem' }}>
            {data.total} document{data.total !== 1 ? 's' : ''}
          </div>
        </div>
      )}
    </div>
  )
}
