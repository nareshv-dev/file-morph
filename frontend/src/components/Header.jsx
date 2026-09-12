import LogoMark from './LogoMark.jsx'
import { navigate } from '../api.js'

export default function Header() {
  function go(event, path) { event.preventDefault(); navigate(path) }
  return (
    <header className="site-header">
      <a className="brand" href="/" onClick={(event) => go(event, '/')} aria-label="FileMorph home">
        <span className="brand-mark"><LogoMark /></span><span>FileMorph</span>
      </a>
      <nav className="site-nav" aria-label="Main navigation">
        <a className="header-cta" href="/convert" onClick={(event) => go(event, '/convert')}>Start converting</a>
      </nav>
    </header>
  )
}
