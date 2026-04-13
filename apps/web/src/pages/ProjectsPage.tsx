import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { projectsApi, type Project } from '../api/client'

const DEFAULT_FORM = {
  name: '',
  description: '',
  status: 'active',
  notes: '',
}

const STATUS_COLORS: Record<string, string> = {
  active: 'active',
  completed: 'active',
  on_hold: 'draft',
  archived: 'archived',
}

export function ProjectsPage() {
  const qc = useQueryClient()
  const [q, setQ] = useState('')
  const [search, setSearch] = useState('')
  const [showModal, setShowModal] = useState(false)
  const [form, setForm] = useState<typeof DEFAULT_FORM>(DEFAULT_FORM)
  const [error, setError] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: ['projects', 'list', search],
    queryFn: () => projectsApi.list({ q: search || undefined, limit: 100 }),
  })

  const createMutation = useMutation({
    mutationFn: (payload: typeof DEFAULT_FORM) => projectsApi.create(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['projects'] })
      setShowModal(false)
      setForm(DEFAULT_FORM)
      setError('')
    },
    onError: (err: any) => {
      setError(err?.response?.data?.detail ?? 'Failed to create project')
    },
  })

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    setSearch(q)
  }

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault()
    const payload = { ...form }
    createMutation.mutate(payload)
  }

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Projects</h1>
        <button className="btn btn-primary" onClick={() => setShowModal(true)}>
          + New Project
        </button>
      </div>

      <form onSubmit={handleSearch} className="search-bar">
        <input
          type="text"
          className="search-input"
          placeholder="Search by name or description…"
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
        <div className="loading">Loading projects…</div>
      ) : !data || data.items.length === 0 ? (
        <div className="empty">
          {search ? `No projects found for "${search}"` : 'No projects yet. Start your first project!'}
        </div>
      ) : (
        <div className="table-container">
          <p style={{ marginBottom: '0.5rem', fontSize: '0.85rem', color: '#6b7280' }}>
            {data.total} project{data.total !== 1 ? 's' : ''}
          </p>
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Description</th>
                <th>Status</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((project: Project) => (
                <tr key={project.id}>
                  <td>
                    <Link to={`/projects/${project.id}`} style={{ fontWeight: 500 }}>
                      {project.name}
                    </Link>
                  </td>
                  <td style={{ color: '#6b7280', fontSize: '0.9rem' }}>{project.description ?? '—'}</td>
                  <td>
                    <span className={`badge badge-${STATUS_COLORS[project.status] ?? 'draft'}`}>
                      {project.status.replace(/_/g, ' ')}
                    </span>
                  </td>
                  <td style={{ fontSize: '0.85rem', color: '#6b7280' }}>
                    {new Date(project.created_at).toLocaleDateString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-title">New Project</div>
            {error && <div className="alert alert-error">{error}</div>}
            <form onSubmit={handleCreate}>
              <div className="form-group">
                <label className="form-label">Name *</label>
                <input
                  className="form-control"
                  required
                  value={form.name}
                  onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                  placeholder="Robot Arm v2"
                />
              </div>
              <div className="form-group">
                <label className="form-label">Description</label>
                <textarea
                  className="form-control"
                  rows={2}
                  value={form.description}
                  onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
                  placeholder="A brief description of the project"
                />
              </div>
              <div className="form-group">
                <label className="form-label">Status</label>
                <select
                  className="form-control"
                  value={form.status}
                  onChange={e => setForm(f => ({ ...f, status: e.target.value }))}
                >
                  <option value="active">Active</option>
                  <option value="on_hold">On Hold</option>
                  <option value="completed">Completed</option>
                  <option value="archived">Archived</option>
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Notes</label>
                <textarea
                  className="form-control"
                  rows={2}
                  value={form.notes}
                  onChange={e => setForm(f => ({ ...f, notes: e.target.value }))}
                />
              </div>
              <div className="form-actions">
                <button type="submit" className="btn btn-primary" disabled={createMutation.isPending}>
                  {createMutation.isPending ? 'Creating…' : 'Create Project'}
                </button>
                <button type="button" className="btn btn-secondary" onClick={() => { setShowModal(false); setError('') }}>
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
