import { useRef, useState } from 'react'
import { CloseIcon, FileIcon, ShieldIcon, UploadIcon } from './Icons.jsx'

const MAX_BYTES = 20 * 1024 * 1024
const MIME_TYPES = {
  pdf: ['application/pdf', 'application/x-pdf'],
  docx: ['application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'application/zip'],
}

function formatBytes(bytes) {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export default function FileUpload({ file, onFile, disabled, error, setError, acceptedExtensions, sourceLabel }) {
  const inputRef = useRef(null)
  const [dragging, setDragging] = useState(false)
  const accept = acceptedExtensions.map((extension) => `.${extension}`).join(',')

  function choose(next) {
    if (!next || disabled) return
    const extension = next.name.split('.').pop()?.toLowerCase()
    const validMime = next.type === '' || (MIME_TYPES[extension] || []).includes(next.type)
    if (!acceptedExtensions.includes(extension) || !validMime) {
      setError(`Choose a ${sourceLabel} file to continue.`)
      return
    }
    if (next.size === 0) {
      setError('This file is empty. Choose a document with content.')
      return
    }
    if (next.size > MAX_BYTES) {
      setError('This file is larger than the 20 MB limit.')
      return
    }
    setError('')
    onFile(next)
  }

  if (file) {
    return (
      <div className="selected-file" aria-label="Selected file">
        <span className="file-icon"><FileIcon /></span>
        <div className="file-copy">
          <strong>{file.name}</strong>
          <span>{file.name.split('.').pop().toUpperCase()} · {formatBytes(file.size)}</span>
        </div>
        <button className="icon-button" type="button" onClick={() => onFile(null)} disabled={disabled} aria-label="Remove selected file"><CloseIcon /></button>
      </div>
    )
  }

  return (
    <>
      <div
        className={`dropzone ${dragging ? 'is-dragging' : ''}`}
        onDragOver={(event) => { event.preventDefault(); if (!disabled) setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => { event.preventDefault(); setDragging(false); choose(event.dataTransfer.files[0]) }}
        onClick={() => !disabled && inputRef.current?.click()}
        onKeyDown={(event) => { if (!disabled && (event.key === 'Enter' || event.key === ' ')) inputRef.current?.click() }}
        role="button"
        tabIndex={disabled ? -1 : 0}
        aria-disabled={disabled}
        aria-label={`Upload a ${sourceLabel} document`}
      >
        <input ref={inputRef} type="file" accept={accept} onChange={(event) => choose(event.target.files[0])} hidden />
        <span className="upload-icon"><UploadIcon /></span>
        <h2>Drop your {sourceLabel} here</h2>
        <p>or <span className="browse-link">browse files</span> from your device</p>
        <div className="file-rules">
          {acceptedExtensions.map((extension) => <span key={extension}>{extension.toUpperCase()}</span>)}
          <span>Up to 20 MB</span>
        </div>
      </div>
      {error && <p className="inline-error" role="alert">{error}</p>}
      <p className="privacy-note"><ShieldIcon /> Your files are processed temporarily and are not permanently stored.</p>
    </>
  )
}
