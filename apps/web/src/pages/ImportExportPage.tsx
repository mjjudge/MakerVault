import { useState, useRef } from 'react'
import { useMutation } from '@tanstack/react-query'
import { apiClient } from '../api/client'

// ---------------------------------------------------------------------------
// Helper – file download from a blob URL
// ---------------------------------------------------------------------------

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------

async function exportCsv(type: 'parts' | 'stock'): Promise<Blob> {
  const res = await apiClient.get(`/import-export/${type}/export`, {
    responseType: 'blob',
  })
  return res.data as Blob
}

async function downloadTemplate(type: 'parts' | 'stock'): Promise<Blob> {
  const res = await apiClient.get(`/import-export/${type}/template`, {
    responseType: 'blob',
  })
  return res.data as Blob
}

interface ImportResult {
  created: number
  skipped: number
  errors: string[]
}

async function importCsv(type: 'parts' | 'stock', file: File): Promise<ImportResult> {
  const form = new FormData()
  form.append('file', file)
  const res = await apiClient.post<ImportResult>(
    `/import-export/${type}/import`,
    form,
    { headers: { 'Content-Type': 'multipart/form-data' } },
  )
  return res.data
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

interface ImportResultBannerProps {
  result: ImportResult
}

function ImportResultBanner({ result }: ImportResultBannerProps) {
  return (
    <div style={{ marginTop: '1rem' }}>
      <div className={`alert ${result.errors.length > 0 ? 'alert-error' : 'alert-success'}`}>
        Import complete — <strong>{result.created}</strong> created,{' '}
        <strong>{result.skipped}</strong> skipped.
        {result.errors.length > 0 && (
          <details style={{ marginTop: '0.5rem' }}>
            <summary style={{ cursor: 'pointer' }}>
              {result.errors.length} warning{result.errors.length !== 1 ? 's' : ''} — click to expand
            </summary>
            <ul style={{ marginTop: '0.5rem', paddingLeft: '1.25rem', fontSize: '0.82rem' }}>
              {result.errors.map((e, i) => <li key={i}>{e}</li>)}
            </ul>
          </details>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export function ImportExportPage() {
  const [partsFile, setPartsFile] = useState<File | null>(null)
  const [stockFile, setStockFile] = useState<File | null>(null)

  const partsFileRef = useRef<HTMLInputElement>(null)
  const stockFileRef = useRef<HTMLInputElement>(null)

  // Export mutations
  const exportParts = useMutation({
    mutationFn: () => exportCsv('parts'),
    onSuccess: (blob) => downloadBlob(blob, 'makervault_parts.csv'),
  })

  const exportStock = useMutation({
    mutationFn: () => exportCsv('stock'),
    onSuccess: (blob) => downloadBlob(blob, 'makervault_stock.csv'),
  })

  // Template download mutations
  const templateParts = useMutation({
    mutationFn: () => downloadTemplate('parts'),
    onSuccess: (blob) => downloadBlob(blob, 'parts_import_template.csv'),
  })

  const templateStock = useMutation({
    mutationFn: () => downloadTemplate('stock'),
    onSuccess: (blob) => downloadBlob(blob, 'stock_import_template.csv'),
  })

  // Import mutations
  const importParts = useMutation({
    mutationFn: (file: File) => importCsv('parts', file),
    onSuccess: () => setPartsFile(null),
  })

  const importStock = useMutation({
    mutationFn: (file: File) => importCsv('stock', file),
    onSuccess: () => setStockFile(null),
  })

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Import &amp; Export</h1>
      </div>

      <p style={{ color: '#6b7280', marginBottom: '2rem', maxWidth: '680px' }}>
        Export your inventory data as CSV for backup or offline use. Import a CSV
        to bulk-add parts or stock items. Use the template downloads to get a
        pre-filled column layout before uploading your own data.
      </p>

      {/* -----------------------------------------------------------------
          Parts section
      ----------------------------------------------------------------- */}
      <section className="card" style={{ marginBottom: '1.5rem' }}>
        <h2 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: '0.25rem' }}>
          Parts catalogue
        </h2>
        <p style={{ color: '#6b7280', fontSize: '0.875rem', marginBottom: '1.25rem' }}>
          Export all parts as a CSV, or import a CSV to add new parts in bulk.
          Rows whose <code>part_code</code> already exists are skipped —
          existing records are never overwritten.
        </p>

        {/* Export + template */}
        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', marginBottom: '1.25rem' }}>
          <button
            className="btn btn-primary"
            title="Download all parts as a CSV file"
            onClick={() => exportParts.mutate()}
            disabled={exportParts.isPending}
          >
            {exportParts.isPending ? 'Exporting…' : '⬇ Export parts CSV'}
          </button>
          <button
            className="btn btn-secondary"
            title="Download a blank CSV template showing the expected columns for importing parts"
            onClick={() => templateParts.mutate()}
            disabled={templateParts.isPending}
          >
            📄 Download parts template
          </button>
        </div>

        {/* Import */}
        <div className="form-group" style={{ marginBottom: 0 }}>
          <label className="form-label" htmlFor="parts-file">
            Import parts CSV
          </label>
          <p style={{ color: '#6b7280', fontSize: '0.8rem', marginBottom: '0.5rem' }}>
            Required columns: <code>part_code</code>, <code>name</code>.
            All other columns are optional.
          </p>
          <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center', flexWrap: 'wrap' }}>
            <input
              id="parts-file"
              ref={partsFileRef}
              type="file"
              accept=".csv"
              title="Select a CSV file to import parts"
              onChange={e => setPartsFile(e.target.files?.[0] ?? null)}
              style={{ fontSize: '0.875rem' }}
            />
            <button
              className="btn btn-primary"
              disabled={!partsFile || importParts.isPending}
              title="Upload and import the selected CSV file"
              onClick={() => {
                if (partsFile) {
                  importParts.mutate(partsFile)
                  if (partsFileRef.current) partsFileRef.current.value = ''
                }
              }}
            >
              {importParts.isPending ? 'Importing…' : '⬆ Import'}
            </button>
          </div>
        </div>

        {importParts.isError && (
          <div className="alert alert-error" style={{ marginTop: '1rem' }}>
            {String((importParts.error as { message?: string })?.message ?? 'Import failed.')}
          </div>
        )}
        {importParts.isSuccess && importParts.data && (
          <ImportResultBanner result={importParts.data} />
        )}
      </section>

      {/* -----------------------------------------------------------------
          Stock section
      ----------------------------------------------------------------- */}
      <section className="card" style={{ marginBottom: '1.5rem' }}>
        <h2 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: '0.25rem' }}>
          Stock items
        </h2>
        <p style={{ color: '#6b7280', fontSize: '0.875rem', marginBottom: '1.25rem' }}>
          Export all stock items as a CSV, or import a CSV to add stock in bulk.
          Each row must reference a <code>part_code</code> that already exists in
          the catalogue, and must include exactly one of <code>location_name</code>{' '}
          or <code>container_name</code>.
        </p>

        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', marginBottom: '1.25rem' }}>
          <button
            className="btn btn-primary"
            title="Download all stock items as a CSV file"
            onClick={() => exportStock.mutate()}
            disabled={exportStock.isPending}
          >
            {exportStock.isPending ? 'Exporting…' : '⬇ Export stock CSV'}
          </button>
          <button
            className="btn btn-secondary"
            title="Download a blank CSV template showing the expected columns for importing stock"
            onClick={() => templateStock.mutate()}
            disabled={templateStock.isPending}
          >
            📄 Download stock template
          </button>
        </div>

        <div className="form-group" style={{ marginBottom: 0 }}>
          <label className="form-label" htmlFor="stock-file">
            Import stock CSV
          </label>
          <p style={{ color: '#6b7280', fontSize: '0.8rem', marginBottom: '0.5rem' }}>
            Required columns: <code>part_code</code>, and one of{' '}
            <code>location_name</code> or <code>container_name</code>.
          </p>
          <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center', flexWrap: 'wrap' }}>
            <input
              id="stock-file"
              ref={stockFileRef}
              type="file"
              accept=".csv"
              title="Select a CSV file to import stock"
              onChange={e => setStockFile(e.target.files?.[0] ?? null)}
              style={{ fontSize: '0.875rem' }}
            />
            <button
              className="btn btn-primary"
              disabled={!stockFile || importStock.isPending}
              title="Upload and import the selected CSV file"
              onClick={() => {
                if (stockFile) {
                  importStock.mutate(stockFile)
                  if (stockFileRef.current) stockFileRef.current.value = ''
                }
              }}
            >
              {importStock.isPending ? 'Importing…' : '⬆ Import'}
            </button>
          </div>
        </div>

        {importStock.isError && (
          <div className="alert alert-error" style={{ marginTop: '1rem' }}>
            {String((importStock.error as { message?: string })?.message ?? 'Import failed.')}
          </div>
        )}
        {importStock.isSuccess && importStock.data && (
          <ImportResultBanner result={importStock.data} />
        )}
      </section>

      {/* -----------------------------------------------------------------
          Tips
      ----------------------------------------------------------------- */}
      <section className="card">
        <h2 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '0.75rem' }}>
          💡 Tips
        </h2>
        <ul style={{ paddingLeft: '1.25rem', fontSize: '0.875rem', color: '#374151', lineHeight: 1.7 }}>
          <li>
            <strong>Encoding:</strong> save CSV files as UTF-8 (most spreadsheet
            applications support this via "Save As → CSV UTF-8").
          </li>
          <li>
            <strong>Boolean columns</strong> (<code>is_consumable</code>, etc.)
            accept <code>true</code> / <code>false</code>, <code>1</code> / <code>0</code>,
            or <code>yes</code> / <code>no</code>.
          </li>
          <li>
            <strong>Tags</strong> in the parts CSV are comma-separated within a
            single cell, e.g. <code>microcontroller,wifi,smd</code>.
          </li>
          <li>
            <strong>Dates</strong> should be ISO 8601 format: <code>YYYY-MM-DD</code>.
          </li>
          <li>
            Importing will never overwrite existing parts — rows with a matching
            <code>part_code</code> are skipped and reported in the warning list.
          </li>
          <li>
            For backup purposes, export both parts and stock after any significant
            inventory change and store the CSV files alongside your{' '}
            <a
              href="https://github.com/mjjudge/MakerVault/blob/main/infra/docker/README.md"
              target="_blank"
              rel="noopener noreferrer"
            >
              database volume backup
            </a>.
          </li>
        </ul>
      </section>
    </div>
  )
}
