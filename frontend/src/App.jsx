import { useEffect, useState } from 'react'
import Header from './components/Header.jsx'
import LandingPage from './components/LandingPage.jsx'
import Workspace from './components/Workspace.jsx'
import PrivacyPage from './components/PrivacyPage.jsx'
import { navigate } from './api.js'

export default function App() {
  const [path, setPath] = useState(window.location.pathname)
  const [user] = useState(null)

  useEffect(() => {
    const follow = () => setPath(window.location.pathname)
    window.addEventListener('popstate', follow)
    return () => window.removeEventListener('popstate', follow)
  }, [])

  let page
  if (path === '/convert') page = <Workspace />
  else if (path === '/privacy') page = <PrivacyPage />
  else if (path === '/unsupported') page = <main id="main" className="history-layout"><section className="page-heading"><h1>Unsupported format.</h1><p>Choose an implemented conversion from FileMorph. Legacy DOC files, password-protected PDFs, scripts, macros, and OCR are not supported.</p><button className="primary-button" onClick={() => navigate('/')}>Choose a format</button></section></main>
  else page = <LandingPage user={user} />

  return <div className="app-shell"><Header user={null} />{page}<footer><span>FileMorph</span><a href="/privacy" onClick={(event) => { event.preventDefault(); navigate('/privacy') }}>Privacy</a></footer></div>
}
