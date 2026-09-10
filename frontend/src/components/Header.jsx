export default function Header() {
  return (
    <header className="site-header">
      <a className="brand" href="/" aria-label="MarkDrop home">
        <span className="brand-mark" aria-hidden="true">M↓</span>
        <span>MarkDrop</span>
      </a>
      <span className="header-note">PDF + DOCX → MD</span>
    </header>
  )
}
