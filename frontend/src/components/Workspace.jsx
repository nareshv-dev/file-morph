import { useState } from 'react'
import FileUpload from './FileUpload.jsx'
import ConversionStatus from './ConversionStatus.jsx'
import MarkdownPreview from './MarkdownPreview.jsx'
import { CheckIcon, CloseIcon, DownloadIcon } from './Icons.jsx'
import { formatBytes } from '../api.js'
import { CONVERSIONS } from '../conversions.js'

export default function Workspace() {
  const initial = CONVERSIONS.find((item) => item.id === sessionStorage.getItem('filemorph-mode')) || CONVERSIONS[0]
  const [mode, setMode] = useState(initial)
  const [file, setFile] = useState(null)
  const [status, setStatus] = useState('idle')
  const [error, setError] = useState('')
  const [job, setJob] = useState(null)
  const [pageRange, setPageRange] = useState('')
  const [preview, setPreview] = useState(null)

  function changeMode(next) { setMode(next); sessionStorage.setItem('filemorph-mode', next.id); setFile(null); setJob(null); setPreview(null); setError(''); setStatus('idle') }
  async function convert() {
    if (!file || status === 'loading') return
    setStatus('loading'); setError(''); setJob(null); setPreview(null)
    const body = new FormData(); body.append('conversion_type', mode.id)
    for (const item of (Array.isArray(file) ? file : [file])) body.append(mode.multiple ? 'files' : 'file', item)
    if (mode.id === 'split-pdf') body.append('page_range', pageRange)
    try {
      const response = await fetch(`/api/convert/${mode.id}`, { method: 'POST', body })
      if (!response.ok) { const data = await response.json().catch(() => ({})); throw new Error(data.error?.message || data.detail || 'Conversion failed.') }
      const output = await response.blob()
      const outputName = response.headers.get('X-Output-Filename') || `${file.name || 'converted'}${mode.targetExtension || ''}`
      setJob({ status: 'completed', output: URL.createObjectURL(output), output_filename: outputName, output_size: output.size })
      setStatus('complete')
    }
    catch (requestError) { setError(requestError.message); setStatus('idle') }
  }
  async function download() {
    try {
      const link = document.createElement('a'); link.href = job.output; link.download = job.output_filename; link.click()
    } catch (requestError) { setError(requestError.message) }
  }
  return <main className="workspace-layout" id="main" tabIndex="-1">
    <section className="workspace-heading"><div><div className="eyebrow"><span /> DIRECT CONVERSION</div><h1>Convert a document.</h1></div><p>Choose a format, add a file, and download the converted result directly.</p></section>
    <label className="format-menu">Conversion format<select value={mode.id} onChange={(event) => changeMode(CONVERSIONS.find((item) => item.id === event.target.value))}>{CONVERSIONS.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}</select></label>
    <section className="converter-card" aria-label={`${mode.title} converter`}>
      <div className="converter-heading"><div><div className="step-label"><span>01</span> Choose a {mode.sourceLabel} document</div><h2>{mode.title}</h2></div></div>
      <FileUpload file={file} onFile={(next) => { setFile(next); setJob(null); setPreview(null); setStatus('idle'); setError('') }} disabled={status === 'loading'} error={error} setError={setError} acceptedExtensions={mode.sourceExtensions} sourceLabel={mode.sourceLabel} multiple={mode.multiple} />
      {mode.id === 'split-pdf' && <label className="range-field">Page range<input placeholder="1-3 or 1,3,5" value={pageRange} onChange={(event) => setPageRange(event.target.value)} /></label>}
      <p className="limitation-note"><strong>Fidelity:</strong> {mode.limitation}</p>
      {status === 'loading' ? <ConversionStatus outputLabel={mode.outputLabel} /> : <button className="primary-button" type="button" disabled={!file} onClick={convert}>Convert to {mode.outputLabel}</button>}
    </section>
    {job && <section className={`job-result ${job.status}`} aria-live="polite"><span className="success-icon"><CheckIcon /></span><div><p>Conversion complete</p><strong>{job.output_filename}</strong><span>{formatBytes(job.output_size)} / ready to download</span></div><button className="primary-button" onClick={download}><DownloadIcon /> Download</button></section>}
    {preview && <MarkdownPreview markdown={preview.markdown} assets={preview.assets} />}
  </main>
}
