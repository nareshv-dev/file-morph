export default function Header({ onHome }) {
  return (
    <header className="site-header">
      <a className="brand" href="/" onClick={(event) => { event.preventDefault(); onHome() }} aria-label="FileMorph home">
        <span className="brand-mark" aria-hidden="true">FM</span>
        <span>FileMorph</span>
      </a>
      <span className="header-note">PDF · DOCX · MD</span>
    </header>
  )
}
