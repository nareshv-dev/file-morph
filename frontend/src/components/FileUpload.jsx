import { useRef, useState } from 'react'
import { CloseIcon, FileIcon, ShieldIcon, UploadIcon } from './Icons.jsx'

const MAX_BYTES = 20 * 1024 * 1024
const ACCEPTED = ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']

function formatBytes(bytes) {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export default function FileUpload({ file, onFile, disabled, error, setError }) {
  const inputRef = useRef(null)
  const [dragging, setDragging] = useState(false)

  function choose(next) {
    if (!next) return
    const extension = next.name.split('.').pop()?.toLowerCase()
    if (!['pdf', 'docx'].includes(extension) || (!ACCEPTED.includes(next.type) && next.type !== '')) {
      setError('Choose a PDF or DOCX file to continue.')
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
        onDragOver={(event) => { event.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => { event.preventDefault(); setDragging(false); choose(event.dataTransfer.files[0]) }}
        onClick={() => inputRef.current?.click()}
        onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') inputRef.current?.click() }}
        role="button"
        tabIndex="0"
        aria-label="Upload a PDF or DOCX document"
      >
        <input ref={inputRef} type="file" accept=".pdf,.docx" onChange={(event) => choose(event.target.files[0])} hidden />
        <span className="upload-icon"><UploadIcon /></span>
        <h2>Drop your document here</h2>
        <p>or <span className="browse-link">browse files</span> from your device</p>
        <div className="file-rules"><span>PDF</span><span>DOCX</span><span>Up to 20 MB</span></div>
      </div>
      {error && <p className="inline-error" role="alert">{error}</p>}
      <p className="privacy-note"><ShieldIcon /> Your files are processed temporarily and are not permanently stored.</p>
    </>
  )
}
