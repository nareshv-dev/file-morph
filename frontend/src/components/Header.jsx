import LogoMark from './LogoMark.jsx'

export default function Header({ onHome }) {
  return (
    <header className="site-header">
      <a className="brand" href="/" onClick={(event) => { event.preventDefault(); onHome() }} aria-label="FileMorph home">
        <span className="brand-mark"><LogoMark /></span>
        <span>FileMorph</span>
      </a>
      <span className="header-note">PDF · DOCX · MD</span>
    </header>
  )
}
