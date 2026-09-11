export default function ConversionStatus({ outputLabel }) {
  return (
    <div className="converting" role="status" aria-live="polite">
      <span className="spinner" aria-hidden="true" />
      <div><strong>Converting your document...</strong><span>Preparing the {outputLabel} file and preserving document content</span></div>
    </div>
  )
}
