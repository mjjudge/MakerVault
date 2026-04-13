import { useQuery } from '@tanstack/react-query'
import { stockApi, type StockItem } from '../api/client'

export function StockPage() {
  const { data, isLoading } = useQuery({
    queryKey: ['stock', 'list'],
    queryFn: () => stockApi.list({ limit: 100 }),
  })

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
                <th>Part ID</th>
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
              {data.items.map((item: StockItem) => (
                <tr key={item.id}>
                  <td style={{ fontFamily: 'monospace', fontSize: '0.8rem', color: '#6b7280' }}>
                    {item.part_id.slice(0, 8)}…
                  </td>
                  <td style={{ fontWeight: 500 }}>{item.quantity}</td>
                  <td>{item.unit ?? '—'}</td>
                  <td><span className={`badge badge-${item.status}`}>{item.status}</span></td>
                  <td>{item.condition ?? '—'}</td>
                  <td style={{ fontFamily: 'monospace', fontSize: '0.8rem', color: '#6b7280' }}>
                    {item.container_id
                      ? `ctr:${item.container_id.slice(0, 8)}…`
                      : item.location_id
                      ? `loc:${item.location_id.slice(0, 8)}…`
                      : '—'}
                  </td>
                  <td>{item.supplier ?? '—'}</td>
                  <td>{item.purchase_date ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
