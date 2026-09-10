import { useMemo, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

export default function MarkdownPreview({ markdown, assets }) {
  const [mode, setMode] = useState('rendered')
  const displayMarkdown = useMemo(() => {
    let value = markdown
    for (const asset of assets) {
      value = value.replaceAll(`(${asset.filename})`, `(data:${asset.content_type};base64,${asset.data})`)
    }
    return value
  }, [markdown, assets])

  function safeUrl(url) {
    if (/^(https?:|mailto:|#|\/)/i.test(url)) return url
    if (/^data:image\/(png|jpe?g|gif|webp|svg\+xml);base64,/i.test(url)) return url
    if (!/^[a-z][a-z0-9+.-]*:/i.test(url)) return url
    return ''
  }

  return (
    <section className="preview-card" aria-labelledby="preview-title">
      <div className="preview-toolbar">
        <h2 id="preview-title">Markdown preview</h2>
        <div className="tabs" role="tablist" aria-label="Preview mode">
          <button role="tab" aria-selected={mode === 'rendered'} className={mode === 'rendered' ? 'active' : ''} onClick={() => setMode('rendered')}>Rendered</button>
          <button role="tab" aria-selected={mode === 'raw'} className={mode === 'raw' ? 'active' : ''} onClick={() => setMode('raw')}>Raw</button>
        </div>
      </div>
      {mode === 'raw' ? <pre className="raw-markdown"><code>{markdown}</code></pre> : (
        <article className="markdown-body">
          <ReactMarkdown remarkPlugins={[remarkGfm]} urlTransform={safeUrl}>{displayMarkdown}</ReactMarkdown>
        </article>
      )}
    </section>
  )
}
