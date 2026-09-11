import { useEffect, useState } from 'react'
import Header from './components/Header.jsx'
import FileUpload from './components/FileUpload.jsx'
import ConversionStatus from './components/ConversionStatus.jsx'
import MarkdownPreview from './components/MarkdownPreview.jsx'
import {
  ArrowIcon,
  CheckIcon,
  DownloadIcon,
  MarkdownIcon,
  PdfIcon,
  RefreshIcon,
  WordIcon,
} from './components/Icons.jsx'

const CONVERSIONS = [
  {
    id: 'pdf-to-docx',
    title: 'PDF to DOCX',
    description: 'Create a Word document that preserves the PDF page layout, text, icons, and images.',
    sourceLabel: 'PDF',
    sourceExtensions: ['pdf'],
    outputLabel: 'DOCX',
    outputExtension: 'docx',
    Icon: PdfIcon,
  },
  {
    id: 'docx-to-pdf',
    title: 'DOCX to PDF',
    description: 'Create a portable PDF from Word text, formatting, tables, and images.',
    sourceLabel: 'DOCX',
    sourceExtensions: ['docx'],
    outputLabel: 'PDF',
    outputExtension: 'pdf',
    Icon: WordIcon,
  },
  {
    id: 'to-markdown',
    title: 'PDF / DOCX to Markdown',
    description: 'Extract document structure and images into clean Markdown files.',
    sourceLabel: 'PDF or DOCX',
    sourceExtensions: ['pdf', 'docx'],
    outputLabel: 'Markdown',
    outputExtension: 'md',
    Icon: MarkdownIcon,
  },
]

function selectedFromHash() {
  const id = window.location.hash.replace(/^#/, '')
  return CONVERSIONS.find((item) => item.id === id) || null
}

function base64Blob(data, type) {
  const bytes = Uint8Array.from(atob(data), (char) => char.charCodeAt(0))
  return new Blob([bytes], { type })
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

async function readError(response) {
  const responseText = await response.text()
  if (responseText) {
    try {
      const payload = JSON.parse(responseText)
      if (payload.error) return payload.error
    } catch {
      // The server may return a plain-text gateway error.
    }
  }
  return response.status >= 500
    ? 'The conversion service is unavailable. Restart the development server and try again.'
    : 'The document could not be converted. Check the file and try again.'
}

async function readMarkdownResponse(response) {
  if (!response.ok) throw new Error(await readError(response))
  const responseText = await response.text()
  let payload
  try {
    payload = JSON.parse(responseText)
  } catch {
    throw new Error('The converter returned an unreadable response. Please try again.')
  }
  if (typeof payload.markdown !== 'string' || !Array.isArray(payload.assets)) {
    throw new Error('The converter returned an incomplete response. Please try again.')
  }
  return payload
}

function suggestedOutputName(sourceName, extension) {
  const stem = sourceName.replace(/\.[^.]+$/, '') || 'converted-document'
  return `${stem}.${extension}`
}

export default function App() {
  const [mode, setMode] = useState(selectedFromHash)
  const [file, setFile] = useState(null)
  const [status, setStatus] = useState('idle')
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)

  useEffect(() => {
    function followBrowserHistory() {
      setMode(selectedFromHash())
      setFile(null)
      setResult(null)
      setError('')
      setStatus('idle')
    }
    window.addEventListener('popstate', followBrowserHistory)
    return () => window.removeEventListener('popstate', followBrowserHistory)
  }, [])

  function clearConversion() {
    setFile(null)
    setResult(null)
    setError('')
    setStatus('idle')
  }

  function chooseMode(nextMode) {
    clearConversion()
    setMode(nextMode)
    window.history.pushState(null, '', `#${nextMode.id}`)
    setTimeout(() => document.getElementById('converter')?.scrollIntoView({ behavior: 'smooth' }), 20)
  }

  function showOptions() {
    clearConversion()
    setMode(null)
    window.history.pushState(null, '', window.location.pathname + window.location.search)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  async function convert() {
    if (!file || !mode || status === 'loading') return
    setStatus('loading')
    setError('')
    const body = new FormData()
    body.append('file', file)
    const controller = new AbortController()
    const timeout = window.setTimeout(() => controller.abort(), 120_000)

    try {
      const response = await fetch(`/api/convert/${mode.id}`, { method: 'POST', body, signal: controller.signal })
      if (mode.id === 'to-markdown') {
        const data = await readMarkdownResponse(response)
        setResult({ kind: 'markdown', ...data })
      } else {
        if (!response.ok) throw new Error(await readError(response))
        const blob = await response.blob()
        const outputFilename = response.headers.get('X-Output-Filename') || suggestedOutputName(file.name, mode.outputExtension)
        setResult({ kind: 'binary', blob, outputFilename })
      }
      setStatus('complete')
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
      <Header onHome={showOptions} />
      <main id="main">
        <section className="hero">
          <div className="eyebrow"><span /> DOCUMENTS, CLEANLY CONVERTED</div>
          <h1>Move documents between<br /><em>the formats you need.</em></h1>
          <p className="hero-copy">Convert PDF and DOCX into Word, PDF, or Markdown while keeping readable content, useful structure, tables, and embedded images.</p>
        </section>

        {!mode ? (
          <section className="format-section" aria-labelledby="format-heading">
            <div className="step-label"><span>01</span> <span id="format-heading" className="step-copy">Choose a conversion</span></div>
            <div className="conversion-grid">
              {CONVERSIONS.map((item) => (
                <button className="conversion-option" type="button" key={item.id} onClick={() => chooseMode(item)}>
                  <span className="conversion-icon"><item.Icon /></span>
                  <span className="conversion-copy"><strong>{item.title}</strong><span>{item.description}</span></span>
                  <span className="conversion-arrow"><ArrowIcon /></span>
                </button>
              ))}
            </div>
          </section>
        ) : (
          <section id="converter" className="converter-card" aria-label={`${mode.title} converter`}>
            <div className="converter-heading">
              <div>
                <div className="step-label"><span>02</span> Choose a {mode.sourceLabel} document</div>
                <h2>{mode.title}</h2>
              </div>
              <button className="back-button" type="button" onClick={showOptions}>Change format</button>
            </div>
            <FileUpload
              file={file}
              onFile={(next) => { setFile(next); setResult(null); setStatus('idle'); setError('') }}
              disabled={status === 'loading'}
              error={error}
              setError={setError}
              acceptedExtensions={mode.sourceExtensions}
              sourceLabel={mode.sourceLabel}
            />
            {file && error && <p className="inline-error" role="alert">{error}</p>}
            {status === 'loading' ? <ConversionStatus outputLabel={mode.outputLabel} /> : (
              <button className="primary-button" type="button" disabled={!file} onClick={convert}>
                Convert to {mode.outputLabel} <span aria-hidden="true">&rarr;</span>
              </button>
            )}
          </section>
        )}

        {result && mode && (
          <section id="result" className="result-section" aria-live="polite">
            <div className="success-heading">
              <span className="success-icon"><CheckIcon /></span>
              <div><p>CONVERSION COMPLETE</p><h2>Your {mode.outputLabel} file is ready.</h2></div>
            </div>

            {result.kind === 'markdown' ? (
              <>
                <div className="result-summary">
                  <div><span>Source</span><strong>{result.original_filename}</strong></div>
                  <div><span>Output</span><strong>{result.markdown_filename}</strong></div>
                  <div><span>Images</span><strong>{result.assets.length} extracted</strong></div>
                </div>
                <div className="result-actions">
                  <button className="primary-button" onClick={() => downloadBlob(new Blob([result.markdown], { type: 'text/markdown;charset=utf-8' }), result.markdown_filename)}><DownloadIcon /> Download .md</button>
                  {result.assets.length > 0 && <button className="secondary-button" onClick={() => downloadBlob(base64Blob(result.bundle, 'application/zip'), result.bundle_filename)}><DownloadIcon /> Download with images</button>}
                  <button className="text-button" onClick={clearConversion}><RefreshIcon /> Convert another</button>
                </div>
                {result.assets.length > 0 && <p className="bundle-hint">Use "Download with images" to keep every Markdown image reference working.</p>}
                <MarkdownPreview markdown={result.markdown} assets={result.assets} />
              </>
            ) : (
              <>
                <div className="result-summary binary-summary">
                  <div><span>Source</span><strong>{file.name}</strong></div>
                  <div><span>Output</span><strong>{result.outputFilename}</strong></div>
                  <div><span>Format</span><strong>{mode.outputLabel}</strong></div>
                </div>
                <div className="result-actions">
                  <button className="primary-button" onClick={() => downloadBlob(result.blob, result.outputFilename)}><DownloadIcon /> Download {mode.outputLabel}</button>
                  <button className="text-button" onClick={clearConversion}><RefreshIcon /> Convert another</button>
                </div>
              </>
            )}
          </section>
        )}
      </main>
      <footer><span>FileMorph</span><span>Temporary processing · No account required</span></footer>
    </div>
  )
}
