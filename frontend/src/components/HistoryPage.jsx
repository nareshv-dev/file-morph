import { useEffect, useRef, useState } from 'react'
import { DownloadIcon, RefreshIcon, TrashIcon } from './Icons.jsx'
import { api, formatBytes, navigate } from '../api.js'

const PAGE_SIZE = 10
const SOURCE_FORMATS = ['pdf', 'docx', 'md', 'markdown', 'html', 'htm', 'txt', 'jpg', 'jpeg', 'png', 'webp']
const TARGET_FORMATS = ['pdf', 'docx', 'md', 'html', 'txt', 'zip']

export default function HistoryPage() {
  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [filters, setFilters] = useState({ search: '', source_format: '', target_format: '', status: '', sort: 'newest' })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const requestSequence = useRef(0)

  async function load(next = filters, nextPage = page) {
    const sequence = ++requestSequence.current
    setLoading(true); setError('')
    try {
      const params = new URLSearchParams({ ...next, page: nextPage, page_size: PAGE_SIZE })
      const data = await api(`/api/history?${params}`)
      if (sequence !== requestSequence.current) return
      setItems(data.items); setTotal(data.total); setPage(nextPage)
    } catch (requestError) {
      if (sequence === requestSequence.current) setError(requestError.message)
    } finally {
      if (sequence === requestSequence.current) setLoading(false)
    }
  }
  useEffect(() => { load() }, [])
  function update(name, value) { const next = { ...filters, [name]: value }; setFilters(next); load(next, 1) }
  async function download(job) {
    try {
      const blob = await api(`/api/conversions/${job.id}/download`)
      const url = URL.createObjectURL(blob); const link = document.createElement('a')
      link.href = url; link.download = job.output_filename; link.click()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch (requestError) { setError(requestError.message) }
  }
  async function retry(job) {
    try { await api(`/api/conversions/${job.id}/retry`, { method: 'POST' }); load() }
    catch (requestError) { setError(requestError.message) }
  }
  async function remove(job) {
    if (!window.confirm(`Permanently delete ${job.source_filename} and its converted file?`)) return
    try { await api(`/api/conversions/${job.id}`, { method: 'DELETE' }); load(filters, 1) }
    catch (requestError) { setError(requestError.message) }
  }
  async function clear() {
    if (!window.confirm('Permanently delete all conversion history, uploaded files, and converted files?')) return
    try { await api('/api/history', { method: 'DELETE' }); load(filters, 1) }
    catch (requestError) { setError(requestError.message) }
  }

  return <main className="history-layout" id="main" tabIndex="-1">
    <section className="page-heading"><div className="eyebrow"><span /> YOUR DOCUMENTS</div><h1>Conversion history.</h1><p>Only you can access these jobs and downloads.</p></section>
    <section className="history-tools" aria-label="History filters">
      <label>Search<input type="search" placeholder="Filename" value={filters.search} onChange={(event) => update('search', event.target.value)} /></label>
      <label>Source<select value={filters.source_format} onChange={(event) => update('source_format', event.target.value)}><option value="">All</option>{SOURCE_FORMATS.map((format) => <option key={format} value={format}>{format.toUpperCase()}</option>)}</select></label>
      <label>Target<select value={filters.target_format} onChange={(event) => update('target_format', event.target.value)}><option value="">All</option>{TARGET_FORMATS.map((format) => <option key={format} value={format}>{format.toUpperCase()}</option>)}</select></label>
      <label>Status<select value={filters.status} onChange={(event) => update('status', event.target.value)}><option value="">All</option>{['queued', 'validating', 'processing', 'completed', 'failed'].map((status) => <option key={status} value={status}>{status}</option>)}</select></label>
      <label>Sort<select value={filters.sort} onChange={(event) => update('sort', event.target.value)}><option value="newest">Newest</option><option value="oldest">Oldest</option></select></label>
    </section>
    {error && <p className="form-error" role="alert">{error}</p>}
    {loading ? <p className="empty-state" role="status">Loading history...</p> : items.length === 0 ? <div className="empty-state"><strong>No conversions found.</strong><span>Your completed and failed jobs will appear here.</span></div> : <section className="history-list" aria-label={`${total} conversion jobs`}>
      {items.map((job) => <article className="history-item" key={job.id}>
        <div className="history-main">
          <span className={`status-badge ${job.status}`}>{job.status}</span>
          <a className="job-title" href={`/conversions/${job.id}`} onClick={(event) => { event.preventDefault(); navigate(`/conversions/${job.id}`) }}>{job.source_filename}</a>
          <span>{job.source_format.toUpperCase()} to {job.target_format.toUpperCase()} / {formatBytes(job.source_size)} to {formatBytes(job.output_size)}</span>
          <time dateTime={job.created_at}>{new Date(job.created_at).toLocaleString()}</time>
          <span className="history-expiration">Expires {new Date(job.expires_at).toLocaleString()}</span>
          {job.failure_reason && <p role="alert">{job.failure_reason}</p>}
        </div>
        <div className="history-actions">
          {job.status === 'completed' && <button className="icon-button" title="Download" aria-label={`Download ${job.output_filename}`} onClick={() => download(job)}><DownloadIcon /></button>}
          <button className="icon-button" title="Retry" aria-label={`Retry ${job.source_filename}`} onClick={() => retry(job)}><RefreshIcon /></button>
          <button className="icon-button danger" title="Delete" aria-label={`Delete ${job.source_filename}`} onClick={() => remove(job)}><TrashIcon /></button>
        </div>
      </article>)}
    </section>}
    <nav className="pagination" aria-label="History pages"><button className="secondary-button" disabled={page <= 1 || loading} onClick={() => load(filters, page - 1)}>Previous</button><span>Page {page} of {Math.max(1, Math.ceil(total / PAGE_SIZE))}</span><button className="secondary-button" disabled={page * PAGE_SIZE >= total || loading} onClick={() => load(filters, page + 1)}>Next</button></nav>
    {total > 0 && <button className="text-button" onClick={clear}><TrashIcon /> Clear all history</button>}
  </main>
}
