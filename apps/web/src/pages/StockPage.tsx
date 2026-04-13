import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { stockApi, partsApi, type StockItem, type Part } from '../api/client'

export function StockPage() {
  const { data, isLoading } = useQuery({
    queryKey: ['stock', 'list'],
    queryFn: () => stockApi.list({ limit: 100 }),
  })

  // Fetch parts map for name display
  const { data: partsData } = useQuery({
    queryKey: ['parts', 'list', ''],
    queryFn: () => partsApi.list({ limit: 200 }),
    enabled: !!data && data.items.length > 0,
  })

  const partMap = new Map<string, Part>()
  if (partsData) {
    for (const p of partsData.items) partMap.set(p.id, p)
  }

  const formatPlacement = (item: StockItem): string => {
    if (item.container_name) return item.container_name
    if (item.location_name) return item.location_name
    if (item.container_id) return `ctr:${item.container_id.slice(0, 8)}…`
    if (item.location_id) return `loc:${item.location_id.slice(0, 8)}…`
    return '—'
  }

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Stock</h1>
      </div>

      {isLoading ? (
        <div className="loading">Loading stock…</div>
      ) : !data || data.items.length === 0 ? (
        <div className="empty">No stock items recorded. Add stock from a part's detail page.</div>
      ) : (
        <div className="table-container">
          <p style={{ marginBottom: '0.5rem', fontSize: '0.85rem', color: '#6b7280' }}>
            {data.total} stock item{data.total !== 1 ? 's' : ''}
          </p>
          <table>
            <thead>
              <tr>
                <th>Part</th>
                <th>Qty</th>
                <th>Unit</th>
                <th>Status</th>
                <th>Condition</th>
                <th>Location / Container</th>
                <th>Supplier</th>
                <th>Purchase Date</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((item: StockItem) => {
                const part = partMap.get(item.part_id)
                return (
                  <tr key={item.id}>
                    <td>
                      {part ? (
                        <Link to={`/parts/${part.id}`} style={{ fontWeight: 500 }}>{part.name}</Link>
                      ) : (
                        <span style={{ fontFamily: 'monospace', fontSize: '0.8rem', color: '#6b7280' }}>
                          {item.part_id.slice(0, 8)}…
                        </span>
                      )}
                    </td>
                    <td style={{ fontWeight: 500 }}>{item.quantity}</td>
                    <td>{item.unit ?? (part?.default_unit ?? '—')}</td>
                    <td><span className={`badge badge-${item.status}`}>{item.status}</span></td>
                    <td>{item.condition ?? '—'}</td>
                    <td>{formatPlacement(item)}</td>
                    <td>{item.supplier ?? '—'}</td>
                    <td>{item.purchase_date ?? '—'}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
