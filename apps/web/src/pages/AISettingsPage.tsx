import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { aiApi, type AIProviderConfig, type HealthCheckResponse } from '../api/client'

const PROVIDER_TYPES = ['openai', 'ollama', 'openai_compatible', 'anthropic'] as const
type ProviderType = typeof PROVIDER_TYPES[number]

const PROVIDER_LABELS: Record<ProviderType, string> = {
  openai: 'OpenAI',
  ollama: 'Ollama (local)',
  openai_compatible: 'OpenAI-compatible endpoint',
  anthropic: 'Anthropic',
}

const PROVIDER_DEFAULTS: Record<ProviderType, { model: string; base_url: string; api_key_env_var: string }> = {
  openai: { model: 'gpt-4o', base_url: '', api_key_env_var: 'OPENAI_API_KEY' },
  ollama: { model: 'llama3', base_url: 'http://ollama:11434', api_key_env_var: '' },
  openai_compatible: { model: 'custom-model', base_url: 'http://localhost:8000', api_key_env_var: '' },
  anthropic: { model: 'claude-3-5-haiku-latest', base_url: '', api_key_env_var: 'ANTHROPIC_API_KEY' },
}

const LOCAL_PROVIDERS: ProviderType[] = ['ollama', 'openai_compatible']

const DEFAULT_FORM = {
  name: '',
  provider_type: 'ollama' as ProviderType,
  base_url: 'http://ollama:11434',
  model: 'llama3',
  api_key_env_var: '',
  is_enabled: true,
  is_default: false,
  notes: '',
}

type FormState = typeof DEFAULT_FORM

export function AISettingsPage() {
  const qc = useQueryClient()

  const [showModal, setShowModal] = useState(false)
  const [editProvider, setEditProvider] = useState<AIProviderConfig | null>(null)
  const [form, setForm] = useState<FormState>(DEFAULT_FORM)
  const [error, setError] = useState('')
  const [healthResults, setHealthResults] = useState<Record<string, HealthCheckResponse>>({})

  const { data: providers = [], isLoading } = useQuery({
    queryKey: ['ai', 'providers'],
    queryFn: () => aiApi.list(),
  })

  const createMutation = useMutation({
    mutationFn: (payload: FormState) =>
      aiApi.create({
        ...payload,
        base_url: payload.base_url || null,
        api_key_env_var: payload.api_key_env_var || null,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['ai', 'providers'] })
      closeModal()
    },
    onError: (err: any) => {
      setError(err?.response?.data?.detail ?? 'Failed to save provider')
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: FormState }) =>
      aiApi.update(id, {
        ...payload,
        base_url: payload.base_url || null,
        api_key_env_var: payload.api_key_env_var || null,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['ai', 'providers'] })
      closeModal()
    },
    onError: (err: any) => {
      setError(err?.response?.data?.detail ?? 'Failed to update provider')
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => aiApi.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['ai', 'providers'] }),
  })

  const healthMutation = useMutation({
    mutationFn: (id: string) => aiApi.healthCheck(id),
    onSuccess: (data, id) => {
      setHealthResults(prev => ({ ...prev, [id]: data }))
    },
  })

  const setDefaultMutation = useMutation({
    mutationFn: (id: string) => aiApi.update(id, { is_default: true }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['ai', 'providers'] }),
  })

  const toggleEnabledMutation = useMutation({
    mutationFn: ({ id, is_enabled }: { id: string; is_enabled: boolean }) =>
      aiApi.update(id, { is_enabled }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['ai', 'providers'] }),
  })

  function openCreate() {
    setEditProvider(null)
    setForm(DEFAULT_FORM)
    setError('')
    setShowModal(true)
  }

  function openEdit(provider: AIProviderConfig) {
    setEditProvider(provider)
    setForm({
      name: provider.name,
      provider_type: provider.provider_type as ProviderType,
      base_url: provider.base_url ?? '',
      model: provider.model,
      api_key_env_var: provider.api_key_env_var ?? '',
      is_enabled: provider.is_enabled,
      is_default: provider.is_default,
      notes: provider.notes ?? '',
    })
    setError('')
    setShowModal(true)
  }

  function closeModal() {
    setShowModal(false)
    setEditProvider(null)
    setForm(DEFAULT_FORM)
    setError('')
  }

  function handleTypeChange(type: ProviderType) {
    const defaults = PROVIDER_DEFAULTS[type]
    setForm(f => ({
      ...f,
      provider_type: type,
      base_url: defaults.base_url,
      model: defaults.model,
      api_key_env_var: defaults.api_key_env_var,
    }))
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (editProvider) {
      updateMutation.mutate({ id: editProvider.id, payload: form })
    } else {
      createMutation.mutate(form)
    }
  }

  function confirmDelete(provider: AIProviderConfig) {
    if (window.confirm(`Delete provider "${provider.name}"? This cannot be undone.`)) {
      deleteMutation.mutate(provider.id)
    }
  }

  const isLocal = LOCAL_PROVIDERS.includes(form.provider_type)
  const isSaving = createMutation.isPending || updateMutation.isPending

  const defaultProvider = providers.find(p => p.is_default && p.is_enabled)

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">AI Settings</h1>
          <p style={{ color: '#6b7280', marginTop: '0.25rem', fontSize: '0.9rem' }}>
            Configure AI providers. API keys are read from environment variables — never stored in the database.
          </p>
        </div>
        <button className="btn btn-primary" onClick={openCreate}>
          + Add Provider
        </button>
      </div>

      {/* Active provider banner */}
      {defaultProvider && (
        <div className="alert alert-success" style={{ marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span>🤖</span>
          <span>
            Active provider: <strong>{defaultProvider.name}</strong>
            {' '}({PROVIDER_LABELS[defaultProvider.provider_type as ProviderType] ?? defaultProvider.provider_type})
            {' · '}{defaultProvider.model}
          </span>
        </div>
      )}
      {!isLoading && providers.length > 0 && !defaultProvider && (
        <div className="alert alert-error" style={{ marginBottom: '1.5rem' }}>
          ⚠️ No default AI provider is set. Set one as default to enable AI features.
        </div>
      )}

      {isLoading ? (
        <div className="loading">Loading providers…</div>
      ) : providers.length === 0 ? (
        <div className="empty">
          <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>🤖</div>
          <div>No AI providers configured yet.</div>
          <div style={{ marginTop: '0.5rem', fontSize: '0.9rem', color: '#6b7280' }}>
            Add Ollama for self-hosted AI, or OpenAI / Anthropic for hosted models.
          </div>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {providers.map(provider => {
            const health = healthResults[provider.id]
            return (
              <div
                key={provider.id}
                className="card"
                style={{
                  opacity: provider.is_enabled ? 1 : 0.6,
                  borderLeft: provider.is_default ? '3px solid #2563eb' : undefined,
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '0.75rem' }}>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                      <span style={{ fontWeight: 600, fontSize: '1rem' }}>{provider.name}</span>
                      {provider.is_default && (
                        <span className="badge badge-active">default</span>
                      )}
                      {!provider.is_enabled && (
                        <span className="badge badge-archived">disabled</span>
                      )}
                      {health && (
                        <span className={`badge badge-${health.healthy ? 'active' : 'archived'}`}>
                          {health.healthy ? '✓ healthy' : '✗ unreachable'}
                        </span>
                      )}
                    </div>
                    <div style={{ marginTop: '0.35rem', fontSize: '0.875rem', color: '#4b5563' }}>
                      <span>{PROVIDER_LABELS[provider.provider_type as ProviderType] ?? provider.provider_type}</span>
                      <span style={{ margin: '0 0.5rem', color: '#d1d5db' }}>·</span>
                      <span>Model: <code>{provider.model}</code></span>
                      {provider.base_url && (
                        <>
                          <span style={{ margin: '0 0.5rem', color: '#d1d5db' }}>·</span>
                          <span>{provider.base_url}</span>
                        </>
                      )}
                    </div>
                    {provider.api_key_env_var && (
                      <div style={{ marginTop: '0.2rem', fontSize: '0.8rem', color: '#6b7280' }}>
                        Key env var: <code>{provider.api_key_env_var}</code>
                      </div>
                    )}
                    {provider.notes && (
                      <div style={{ marginTop: '0.25rem', fontSize: '0.82rem', color: '#6b7280', fontStyle: 'italic' }}>
                        {provider.notes}
                      </div>
                    )}
                    {health?.detail && !health.healthy && (
                      <div style={{ marginTop: '0.25rem', fontSize: '0.82rem', color: '#dc2626' }}>
                        {health.detail}
                      </div>
                    )}
                  </div>

                  <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', alignItems: 'center' }}>
                    <button
                      className="btn btn-secondary"
                      style={{ fontSize: '0.8rem', padding: '0.3rem 0.65rem' }}
                      disabled={healthMutation.isPending}
                      onClick={() => healthMutation.mutate(provider.id)}
                    >
                      Test
                    </button>
                    {!provider.is_default && (
                      <button
                        className="btn btn-secondary"
                        style={{ fontSize: '0.8rem', padding: '0.3rem 0.65rem' }}
                        onClick={() => setDefaultMutation.mutate(provider.id)}
                      >
                        Set default
                      </button>
                    )}
                    <button
                      className="btn btn-secondary"
                      style={{ fontSize: '0.8rem', padding: '0.3rem 0.65rem' }}
                      onClick={() =>
                        toggleEnabledMutation.mutate({
                          id: provider.id,
                          is_enabled: !provider.is_enabled,
                        })
                      }
                    >
                      {provider.is_enabled ? 'Disable' : 'Enable'}
                    </button>
                    <button
                      className="btn btn-secondary"
                      style={{ fontSize: '0.8rem', padding: '0.3rem 0.65rem' }}
                      onClick={() => openEdit(provider)}
                    >
                      Edit
                    </button>
                    <button
                      className="btn btn-danger"
                      style={{ fontSize: '0.8rem', padding: '0.3rem 0.65rem' }}
                      onClick={() => confirmDelete(provider)}
                    >
                      Delete
                    </button>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Help text */}
      <div className="card" style={{ marginTop: '2rem', background: '#f9fafb' }}>
        <h3 style={{ marginTop: 0, marginBottom: '0.75rem', fontSize: '0.95rem', color: '#374151' }}>
          💡 How AI providers work
        </h3>
        <ul style={{ margin: 0, paddingLeft: '1.25rem', fontSize: '0.875rem', color: '#6b7280', lineHeight: 1.6 }}>
          <li>API keys are <strong>never stored in the database</strong>. Set them as environment variables on the host.</li>
          <li>The <strong>api_key_env_var</strong> field records which env var to read at runtime (e.g. <code>OPENAI_API_KEY</code>).</li>
          <li>For <strong>Ollama</strong>: run <code>ollama pull llama3</code> on the host and point to <code>http://ollama:11434</code>.</li>
          <li>For <strong>OpenAI</strong>: set <code>OPENAI_API_KEY</code> in <code>infra/docker/.env</code>.</li>
          <li>Only the <strong>default</strong> enabled provider is used for AI tasks. Use "Set default" to switch.</li>
        </ul>
      </div>

      {/* Create / Edit modal */}
      {showModal && (
        <div className="modal-overlay" onClick={closeModal}>
          <div className="modal" style={{ maxWidth: '520px' }} onClick={e => e.stopPropagation()}>
            <div className="modal-title">{editProvider ? 'Edit Provider' : 'Add AI Provider'}</div>
            {error && <div className="alert alert-error">{error}</div>}
            <form onSubmit={handleSubmit}>
              <div className="form-group">
                <label className="form-label">Display name *</label>
                <input
                  className="form-control"
                  required
                  value={form.name}
                  onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                  placeholder="Local Ollama"
                />
              </div>

              <div className="form-group">
                <label className="form-label">Provider type *</label>
                <select
                  className="form-control"
                  value={form.provider_type}
                  onChange={e => handleTypeChange(e.target.value as ProviderType)}
                >
                  {PROVIDER_TYPES.map(t => (
                    <option key={t} value={t}>{PROVIDER_LABELS[t]}</option>
                  ))}
                </select>
              </div>

              {isLocal && (
                <div className="form-group">
                  <label className="form-label">Base URL *</label>
                  <input
                    className="form-control"
                    required
                    value={form.base_url}
                    onChange={e => setForm(f => ({ ...f, base_url: e.target.value }))}
                    placeholder="http://ollama:11434"
                  />
                  <div style={{ fontSize: '0.8rem', color: '#6b7280', marginTop: '0.25rem' }}>
                    Full URL of the provider endpoint (no trailing slash).
                  </div>
                </div>
              )}

              <div className="form-group">
                <label className="form-label">Model *</label>
                <input
                  className="form-control"
                  required
                  value={form.model}
                  onChange={e => setForm(f => ({ ...f, model: e.target.value }))}
                  placeholder="llama3"
                />
              </div>

              {!isLocal && (
                <div className="form-group">
                  <label className="form-label">API key environment variable</label>
                  <input
                    className="form-control"
                    value={form.api_key_env_var}
                    onChange={e => setForm(f => ({ ...f, api_key_env_var: e.target.value }))}
                    placeholder="OPENAI_API_KEY"
                  />
                  <div style={{ fontSize: '0.8rem', color: '#6b7280', marginTop: '0.25rem' }}>
                    The <em>name</em> of the env var holding the key — the key itself is never saved here.
                  </div>
                </div>
              )}

              <div className="form-group" style={{ display: 'flex', gap: '1.5rem' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', cursor: 'pointer', fontSize: '0.9rem' }}>
                  <input
                    type="checkbox"
                    checked={form.is_enabled}
                    onChange={e => setForm(f => ({ ...f, is_enabled: e.target.checked }))}
                  />
                  Enabled
                </label>
                <label style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', cursor: 'pointer', fontSize: '0.9rem' }}>
                  <input
                    type="checkbox"
                    checked={form.is_default}
                    onChange={e => setForm(f => ({ ...f, is_default: e.target.checked }))}
                  />
                  Set as default
                </label>
              </div>

              <div className="form-group">
                <label className="form-label">Notes</label>
                <textarea
                  className="form-control"
                  rows={2}
                  value={form.notes}
                  onChange={e => setForm(f => ({ ...f, notes: e.target.value }))}
                  placeholder="Optional notes about this provider"
                />
              </div>

              <div className="form-actions">
                <button type="submit" className="btn btn-primary" disabled={isSaving}>
                  {isSaving ? 'Saving…' : editProvider ? 'Save Changes' : 'Add Provider'}
                </button>
                <button type="button" className="btn btn-secondary" onClick={closeModal}>
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
