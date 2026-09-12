import { useRef, useState } from 'react'
import { CloseIcon, FileIcon, ShieldIcon, UploadIcon } from './Icons.jsx'

const MAX_BYTES = 20 * 1024 * 1024
const MIME_TYPES = {
  pdf: ['application/pdf', 'application/x-pdf'],
  docx: ['application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'application/zip'],
  md: ['text/markdown', 'text/plain'], markdown: ['text/markdown', 'text/plain'],
  html: ['text/html', 'application/xhtml+xml', 'text/plain'], htm: ['text/html', 'application/xhtml+xml', 'text/plain'],
  txt: ['text/plain'], jpg: ['image/jpeg'], jpeg: ['image/jpeg'], png: ['image/png'], webp: ['image/webp'],
}

function formatBytes(bytes) { return bytes < 1024 * 1024 ? `${(bytes / 1024).toFixed(1)} KB` : `${(bytes / (1024 * 1024)).toFixed(1)} MB` }

export default function FileUpload({ file, onFile, disabled, error, setError, acceptedExtensions, sourceLabel, multiple = false }) {
  const inputRef = useRef(null)
  const [dragging, setDragging] = useState(false)
  const accept = acceptedExtensions.map((extension) => `.${extension}`).join(',')

  function choose(list) {
    const selected = Array.from(list || [])
    if (!selected.length || disabled) return
    if ((!multiple && selected.length > 1) || selected.length > 20) { setError('Choose a supported number of files (maximum 20).'); return }
    for (const next of selected) {
      const extension = next.name.split('.').pop()?.toLowerCase()
      const validMime = next.type === '' || (MIME_TYPES[extension] || []).includes(next.type)
      if (!acceptedExtensions.includes(extension) || !validMime) { setError(`Choose a ${sourceLabel} file to continue.`); return }
      if (next.size === 0) { setError('This file is empty. Choose a document with content.'); return }
    }
    if (selected.reduce((total, next) => total + next.size, 0) > MAX_BYTES) { setError('Combined files exceed the 20 MB limit.'); return }
    setError(''); onFile(multiple ? selected : selected[0])
  }

  if (file) {
    const selected = Array.isArray(file) ? file : [file]
    return <div className="selected-file" aria-label="Selected files"><span className="file-icon"><FileIcon /></span><div className="file-copy"><strong>{selected.map((item) => item.name).join(', ')}</strong><span>{selected.length} file{selected.length === 1 ? '' : 's'} · {formatBytes(selected.reduce((total, item) => total + item.size, 0))}</span></div><button className="icon-button" type="button" onClick={() => onFile(null)} disabled={disabled} aria-label="Remove selected files"><CloseIcon /></button></div>
  }

  return <>
    <div className={`dropzone ${dragging ? 'is-dragging' : ''}`} onDragOver={(event) => { event.preventDefault(); if (!disabled) setDragging(true) }} onDragLeave={() => setDragging(false)} onDrop={(event) => { event.preventDefault(); setDragging(false); choose(event.dataTransfer.files) }} onClick={() => !disabled && inputRef.current?.click()} onKeyDown={(event) => { if (!disabled && (event.key === 'Enter' || event.key === ' ')) { event.preventDefault(); inputRef.current?.click() } }} role="button" tabIndex={disabled ? -1 : 0} aria-disabled={disabled} aria-label={`Upload ${multiple ? 'files' : 'a file'} for ${sourceLabel}`}>
      <input ref={inputRef} type="file" accept={accept} multiple={multiple} onChange={(event) => choose(event.target.files)} hidden />
      <span className="upload-icon"><UploadIcon /></span><h2>Drop your {sourceLabel} here</h2><p>or <span className="browse-link">browse files</span> from your device</p><div className="file-rules">{acceptedExtensions.map((extension) => <span key={extension}>{extension.toUpperCase()}</span>)}<span>Up to 20 MB total</span></div>
    </div>
    {error && <p className="inline-error" role="alert">{error}</p>}
    <p className="privacy-note"><ShieldIcon /> Stored privately for 24 hours, or until you delete the conversion.</p>
  </>
}
