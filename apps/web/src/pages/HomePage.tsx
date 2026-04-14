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
            <Link to="/import-export" className="btn btn-secondary">Import / Export</Link>
            <a href="/api/docs" target="_blank" rel="noopener noreferrer" className="btn btn-secondary">
              API Docs ↗
            </a>
          </div>
        </div>
      )}

      {/* How-to workflow guide */}
      {!search && (
        <div style={{ marginTop: '2.5rem' }}>
          <h2 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: '0.5rem', color: '#374151' }}>
            How to use MakerVault
          </h2>
          <p style={{ color: '#6b7280', fontSize: '0.875rem', marginBottom: '1.25rem' }}>
            Follow this workflow to get the most out of your inventory system.
          </p>

          <div className="howto-steps">
            <div className="howto-step">
              <div className="howto-step-number">1</div>
              <div>
                <strong>Set up locations and containers</strong>
                <p>
                  Go to <Link to="/locations">Locations</Link> and add the physical places
                  where you store parts — rooms, shelves, or buildings. Inside each location
                  you can create <em>containers</em> (boxes, trays, drawers) which can
                  nest inside each other. Every container can be given a label code for
                  quick physical identification.
                </p>
              </div>
            </div>

            <div className="howto-step">
              <div className="howto-step-number">2</div>
              <div>
                <strong>Add parts to the catalogue</strong>
                <p>
                  Go to <Link to="/parts">Parts</Link> and click <em>+ New Part</em>.
                  Give the part a unique code, a name, and fill in the spec fields you know.
                  You can always come back to add more detail later — including documents
                  such as datasheets and pinout diagrams.
                </p>
              </div>
            </div>

            <div className="howto-step">
              <div className="howto-step-number">3</div>
              <div>
                <strong>Record your stock</strong>
                <p>
                  From a part's detail page, add one or more <em>stock items</em> to
                  record where the physical parts are stored and how many you have.
                  You can also view and manage all stock from the{' '}
                  <Link to="/stock">Stock</Link> page.
                </p>
              </div>
            </div>

            <div className="howto-step">
              <div className="howto-step-number">4</div>
              <div>
                <strong>Create projects with a Bill of Materials</strong>
                <p>
                  Go to <Link to="/projects">Projects</Link> to track what you are
                  building. Add parts to the BOM with required quantities and MakerVault
                  will tell you instantly whether you have enough stock to build the project.
                </p>
              </div>
            </div>

            <div className="howto-step">
              <div className="howto-step-number">5</div>
              <div>
                <strong>Use AI enrichment and inspiration</strong>
                <p>
                  Configure an AI provider in <Link to="/ai">AI Settings</Link> (Ollama
                  runs locally with no internet required). Then use{' '}
                  <Link to="/suggestions">Inspire</Link> to ask what you could build with
                  your current stock, or open any part's detail page to enrich its
                  description and tags from an attached datasheet.
                </p>
              </div>
            </div>

            <div className="howto-step">
              <div className="howto-step-number">6</div>
              <div>
                <strong>Track usage and keep history</strong>
                <p>
                  Record stock consumption, returns, or test events from the{' '}
                  <Link to="/history">History</Link> page. Events can be linked to a
                  project and automatically adjust stock quantities.
                </p>
              </div>
            </div>

            <div className="howto-step">
              <div className="howto-step-number">7</div>
              <div>
                <strong>Import in bulk &amp; back up regularly</strong>
                <p>
                  Use <Link to="/import-export">Import / Export</Link> to load large
                  parts lists or stock from a spreadsheet CSV, and to export your data
                  for offline backup. Pair CSV exports with regular Docker volume
                  snapshots for a complete backup strategy.
                </p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
