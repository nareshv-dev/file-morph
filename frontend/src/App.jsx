import { useState } from 'react'
import Header from './components/Header.jsx'
import FileUpload from './components/FileUpload.jsx'
import ConversionStatus from './components/ConversionStatus.jsx'
import MarkdownPreview from './components/MarkdownPreview.jsx'
import { CheckIcon, DownloadIcon, ImageIcon, RefreshIcon } from './components/Icons.jsx'

function base64Blob(data, type) {
  const bytes = Uint8Array.from(atob(data), (char) => char.charCodeAt(0))
  return new Blob([bytes], { type })
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

async function readApiResponse(response) {
  const responseText = await response.text()
  let payload = {}

  if (responseText) {
    try {
      payload = JSON.parse(responseText)
    } catch {
      if (response.ok) {
        throw new Error('The converter returned an unreadable response. Please try again.')
      }
    }
  }

  if (!response.ok) {
    if (payload.error) throw new Error(payload.error)
    if (response.status >= 500) {
      throw new Error('The conversion service is unavailable. Restart the development server and try again.')
    }
    throw new Error('The document could not be converted. Check the file and try again.')
  }

  if (typeof payload.markdown !== 'string' || !Array.isArray(payload.assets)) {
    throw new Error('The converter returned an incomplete response. Please try again.')
  }
  return payload
}

export default function App() {
  const [file, setFile] = useState(null)
  const [status, setStatus] = useState('idle')
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)

  function reset() {
    setFile(null); setResult(null); setError(''); setStatus('idle')
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  async function convert() {
    if (!file || status === 'loading') return
    setStatus('loading'); setError('')
    const body = new FormData()
    body.append('file', file)
    const controller = new AbortController()
    const timeout = window.setTimeout(() => controller.abort(), 120_000)
    try {
      const response = await fetch('/api/convert', { method: 'POST', body, signal: controller.signal })
      const data = await readApiResponse(response)
      setResult(data); setStatus('complete')
      setTimeout(() => document.getElementById('result')?.scrollIntoView({ behavior: 'smooth' }), 50)
    } catch (requestError) {
      const message = requestError.name === 'AbortError'
        ? 'Conversion took too long. Try a smaller document or try again.'
        : requestError.message === 'Failed to fetch'
          ? 'Could not reach the conversion service. Restart the development server and try again.'
          : requestError.message
      setError(message)
      setStatus('idle')
    } finally {
      window.clearTimeout(timeout)
    }
  }

  return (
    <div className="app-shell">
      <Header />
      <main id="main">
        <section className="hero">
          <div className="eyebrow"><span /> DOCUMENTS, CLEANLY CONVERTED</div>
          <h1>Turn documents into<br /><em>clean Markdown.</em></h1>
          <p className="hero-copy">Preserve headings, tables, links, lists, and images from your PDF or DOCX—without uploading them to permanent storage.</p>
        </section>

        <section className="converter-card" aria-label="Document converter">
          <div className="step-label"><span>01</span> Choose a document</div>
          <FileUpload file={file} onFile={(next) => { setFile(next); setResult(null); setStatus('idle'); setError('') }} disabled={status === 'loading'} error={error} setError={setError} />
          {file && error && <p className="inline-error" role="alert">{error}</p>}
          {status === 'loading' ? <ConversionStatus /> : (
            <button className="primary-button" type="button" disabled={!file} onClick={convert}>
              Convert to Markdown <span aria-hidden="true">→</span>
            </button>
          )}
        </section>

        {result && (
          <section id="result" className="result-section" aria-live="polite">
            <div className="success-heading">
              <span className="success-icon"><CheckIcon /></span>
              <div><p>CONVERSION COMPLETE</p><h2>Your Markdown is ready.</h2></div>
            </div>
            <div className="result-summary">
              <div><span>Source</span><strong>{result.original_filename}</strong></div>
              <div><span>Output</span><strong>{result.markdown_filename}</strong></div>
              <div><span>Images</span><strong>{result.assets.length} extracted</strong></div>
            </div>
            <div className="result-actions">
              <button className="primary-button" onClick={() => downloadBlob(new Blob([result.markdown], { type: 'text/markdown;charset=utf-8' }), result.markdown_filename)}><DownloadIcon /> Download .md</button>
              {result.assets.length > 0 && <button className="secondary-button" onClick={() => downloadBlob(base64Blob(result.bundle, 'application/zip'), result.bundle_filename)}><ImageIcon /> Download with images</button>}
              <button className="text-button" onClick={reset}><RefreshIcon /> Convert another</button>
            </div>
            {result.assets.length > 0 && <p className="bundle-hint">Use “Download with images” to keep every Markdown image reference working.</p>}
            <MarkdownPreview markdown={result.markdown} assets={result.assets} />
          </section>
        )}
      </main>
      <footer><span>MarkDrop</span><span>Local-first simplicity · No account required</span></footer>
    </div>
  )
}
