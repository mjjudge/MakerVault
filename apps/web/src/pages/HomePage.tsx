import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { partsApi, stockApi, locationsApi, type Part } from '../api/client'

export function HomePage() {
  const [query, setQuery] = useState('')
  const [search, setSearch] = useState('')

  const { data: partsData, isLoading: partsLoading } = useQuery({
    queryKey: ['parts', 'count'],
    queryFn: () => partsApi.list({ limit: 1 }),
  })

  const { data: stockData } = useQuery({
    queryKey: ['stock', 'count'],
    queryFn: () => stockApi.list({ limit: 1 }),
  })

  const { data: locationsData } = useQuery({
    queryKey: ['locations', 'count'],
    queryFn: () => locationsApi.list({ limit: 1 }),
  })

  const { data: searchResults, isLoading: searchLoading } = useQuery({
    queryKey: ['parts', 'search', search],
    queryFn: () => partsApi.list({ q: search, limit: 20 }),
    enabled: search.length > 0,
  })

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    setSearch(query)
  }

  return (
    <div>
      <div style={{ marginBottom: '2rem' }}>
        <h1 className="page-title" style={{ marginBottom: '0.5rem' }}>MakerVault</h1>
        <p style={{ color: '#6b7280' }}>
          Self-hosted inventory and knowledge system for electronics and workshop parts.
        </p>
      </div>

      {/* Stats */}
      <div className="stats-row">
        <div className="stat-card">
          <div className="stat-label">Parts</div>
          <div className="stat-value">{partsLoading ? '…' : (partsData?.total ?? 0)}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Stock Items</div>
          <div className="stat-value">{stockData?.total ?? 0}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Locations</div>
          <div className="stat-value">{locationsData?.total ?? 0}</div>
        </div>
      </div>

      {/* Search */}
      <form onSubmit={handleSearch} className="search-bar">
        <input
          type="text"
          className="search-input"
          placeholder="Search parts by name, code, manufacturer…"
          value={query}
          onChange={e => setQuery(e.target.value)}
          autoFocus
        />
        <button type="submit" className="btn btn-primary">Search</button>
        {search && (
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => { setQuery(''); setSearch('') }}
          >
            Clear
          </button>
        )}
      </form>

      {/* Search results */}
      {search && (
        <div>
          {searchLoading ? (
            <div className="loading">Searching…</div>
          ) : searchResults && searchResults.items.length > 0 ? (
            <>
              <p style={{ marginBottom: '1rem', color: '#6b7280', fontSize: '0.9rem' }}>
                {searchResults.total} result{searchResults.total !== 1 ? 's' : ''} for "{search}"
              </p>
              <div className="table-container">
                <table>
                  <thead>
                    <tr>
                      <th>Part Code</th>
                      <th>Name</th>
                      <th>Kind</th>
                      <th>Manufacturer</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {searchResults.items.map((part: Part) => (
                      <tr key={part.id}>
                        <td>
                          <Link to={`/parts/${part.id}`} style={{ fontFamily: 'monospace' }}>
                            {part.part_code}
                          </Link>
                        </td>
                        <td>{part.name}</td>
                        <td>{part.part_kind ?? '—'}</td>
                        <td>{part.manufacturer ?? '—'}</td>
                        <td>
                          <span className={`badge badge-${part.status}`}>{part.status}</span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          ) : (
            <div className="empty">No parts found for "{search}"</div>
          )}
        </div>
      )}

      {/* Quick links when not searching */}
      {!search && (
        <div style={{ marginTop: '2rem' }}>
          <h2 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: '1rem', color: '#374151' }}>
            Quick access
          </h2>
          <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
            <Link to="/parts" className="btn btn-secondary">Browse Parts</Link>
            <Link to="/stock" className="btn btn-secondary">View Stock</Link>
            <Link to="/locations" className="btn btn-secondary">Locations</Link>
            <a href="/api/docs" target="_blank" rel="noopener noreferrer" className="btn btn-secondary">
              API Docs ↗
            </a>
          </div>
        </div>
      )}
    </div>
  )
}
