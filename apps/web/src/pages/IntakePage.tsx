import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { intakeApi, type IntakeMatchResponse, type IntakeCandidate, type StorageSuggestion } from '../api/client'

export function IntakePage() {
  const navigate = useNavigate()
  const [description, setDescription] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState<IntakeMatchResponse | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!description.trim()) return
    setLoading(true)
    setError('')
    setResult(null)
    try {
      const data = await intakeApi.match(description.trim())
      setResult(data)
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? 'Something went wrong. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  const handleReset = () => {
    setDescription('')
    setResult(null)
    setError('')
  }

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Part Intake</h1>
      </div>

      <p style={{ marginBottom: '1.25rem', color: '#6b7280', maxWidth: '640px' }}>
        Describe a part in plain English — for example <em>"10k resistor 0603"</em>, <em>"ESP32 dev board"</em>, or <em>"DHT22 temp sensor"</em>. MakerVault will suggest any matching parts already in your inventory, a unique part code if you are adding something new, and likely storage locations based on past placements.
      </p>

      <form onSubmit={handleSubmit} style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.5rem', maxWidth: '640px' }}>
        <input
          type="text"
          className="search-input"
          placeholder="Describe the part…"
          value={description}
          onChange={e => setDescription(e.target.value)}
          style={{ flex: 1 }}
          autoFocus
        />
        <button type="submit" className="btn btn-primary" disabled={loading || !description.trim()}>
          {loading ? 'Searching…' : 'Match'}
        </button>
        {result && (
          <button type="button" className="btn btn-secondary" onClick={handleReset}>
            Reset
          </button>
        )}
      </form>

      {error && <div className="alert alert-error">{error}</div>}

      {result && (
        <div>
          {/* Normalised tokens */}
          {result.normalised_tokens.length > 0 && (
            <p style={{ fontSize: '0.85rem', color: '#6b7280', marginBottom: '1.25rem' }}>
              Tokens:{' '}
              {result.normalised_tokens.map(t => (
                <span
                  key={t}
                  style={{
                    display: 'inline-block',
                    background: '#f3f4f6',
                    borderRadius: '4px',
                    padding: '1px 6px',
                    marginRight: '4px',
                    fontFamily: 'monospace',
                    fontSize: '0.8rem',
                  }}
                >
                  {t}
                </span>
              ))}
            </p>
          )}

          {/* Candidates */}
          <section style={{ marginBottom: '2rem' }}>
            <h2 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: '0.75rem' }}>
              Matching parts in inventory
            </h2>
            {result.candidates.length === 0 ? (
              <p style={{ color: '#6b7280' }}>No close matches found — this looks like a new part.</p>
            ) : (
              <div className="table-container">
                <table>
                  <thead>
                    <tr>
                      <th>Confidence</th>
                      <th>Part Code</th>
                      <th>Name</th>
                      <th>Kind</th>
                      <th>MPN</th>
                      <th>Why matched</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.candidates.map((c: IntakeCandidate) => (
                      <tr key={c.part_id}>
                        <td>
                          <ConfidenceBadge confidence={c.confidence} />
                        </td>
                        <td style={{ fontFamily: 'monospace', fontWeight: 500 }}>{c.part_code}</td>
                        <td>{c.name}</td>
                        <td>{c.part_kind ?? '—'}</td>
                        <td>{c.manufacturer_part_number ?? '—'}</td>
                        <td style={{ fontSize: '0.8rem', color: '#6b7280' }}>{c.match_reason}</td>
                        <td>
                          <button
                            className="btn btn-secondary"
                            style={{ fontSize: '0.8rem', padding: '2px 10px' }}
                            onClick={() => navigate(`/parts/${c.part_id}`)}
                          >
                            View
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          {/* Suggested part code */}
          <section style={{ marginBottom: '2rem' }}>
            <h2 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: '0.75rem' }}>
              Suggested part code (new part)
            </h2>
            <div
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.75rem',
                background: '#f0fdf4',
                border: '1px solid #bbf7d0',
                borderRadius: '6px',
                padding: '0.5rem 1rem',
              }}
            >
              <span style={{ fontFamily: 'monospace', fontWeight: 600, fontSize: '1rem' }}>
                {result.suggested_part_code}
              </span>
              <button
                className="btn btn-secondary"
                style={{ fontSize: '0.8rem', padding: '2px 10px' }}
                onClick={() => {
                  navigator.clipboard.writeText(result.suggested_part_code).catch(() => {})
                }}
              >
                Copy
              </button>
              <button
                className="btn btn-primary"
                style={{ fontSize: '0.8rem', padding: '2px 10px' }}
                onClick={() => navigate(`/parts?new=1&part_code=${encodeURIComponent(result.suggested_part_code)}`)}
              >
                Create part →
              </button>
            </div>
            <p style={{ fontSize: '0.8rem', color: '#6b7280', marginTop: '0.4rem' }}>
              This code is unique in your current inventory.
            </p>
          </section>

          {/* Storage suggestions */}
          <section style={{ marginBottom: '2rem' }}>
            <h2 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: '0.75rem' }}>
              Suggested storage locations
            </h2>
            {result.storage_suggestions.length === 0 ? (
              <p style={{ color: '#6b7280' }}>
                No historical placement pattern found. Choose any location or container when adding stock.
              </p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', maxWidth: '480px' }}>
                {result.storage_suggestions.map((s: StorageSuggestion, i) => (
                  <div
                    key={i}
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      padding: '0.5rem 0.75rem',
                      background: '#f9fafb',
                      border: '1px solid #e5e7eb',
                      borderRadius: '6px',
                    }}
                  >
                    <div>
                      <span style={{ fontWeight: 500 }}>{s.name}</span>
                      <span style={{ fontSize: '0.8rem', color: '#6b7280', marginLeft: '0.5rem' }}>
                        {s.location_id ? 'location' : 'container'}
                      </span>
                      <div style={{ fontSize: '0.78rem', color: '#9ca3af', marginTop: '1px' }}>{s.reason}</div>
                    </div>
                    <ConfidenceBadge confidence={s.score} />
                  </div>
                ))}
              </div>
            )}
          </section>
        </div>
      )}
    </div>
  )
}

function ConfidenceBadge({ confidence }: { confidence: number }) {
  const color =
    confidence >= 70
      ? { bg: '#dcfce7', text: '#166534' }
      : confidence >= 40
      ? { bg: '#fef9c3', text: '#854d0e' }
      : { bg: '#fee2e2', text: '#991b1b' }
  return (
    <span
      style={{
        display: 'inline-block',
        background: color.bg,
        color: color.text,
        borderRadius: '9999px',
        padding: '1px 8px',
        fontSize: '0.78rem',
        fontWeight: 600,
        minWidth: '38px',
        textAlign: 'center',
      }}
    >
      {confidence}%
    </span>
  )
}
