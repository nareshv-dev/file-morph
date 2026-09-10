export default function ConversionStatus() {
  return (
    <div className="converting" role="status" aria-live="polite">
      <span className="spinner" aria-hidden="true" />
      <div><strong>Converting your document…</strong><span>Preserving structure and extracting images</span></div>
    </div>
  )
}
