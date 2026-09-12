import { ArrowIcon } from './Icons.jsx'
import { CONVERSIONS } from '../conversions.js'
import { navigate } from '../api.js'

export default function LandingPage() {
  function choose(mode) { sessionStorage.setItem('filemorph-mode', mode.id); navigate('/convert') }
  return <main id="main" tabIndex="-1">
    <section className="hero">
      <div className="eyebrow"><span /> DOCUMENTS, CLEANLY CONVERTED</div>
      <h1><em>FileMorph</em></h1>
      <p className="hero-copy">Convert documents and images between the formats you need. Your files are processed for the conversion and downloaded directly to your device.</p>
    </section>
    <section className="format-section" aria-labelledby="format-heading">
      <div className="step-label"><span>01</span> <span id="format-heading" className="step-copy">Choose a conversion</span></div>
      <div className="conversion-grid">{CONVERSIONS.map((item) => <button className="conversion-option" type="button" key={item.id} onClick={() => choose(item)}><span className="conversion-icon"><item.Icon /></span><span className="conversion-copy"><strong>{item.title}</strong><span>{item.description}</span></span><span className="conversion-arrow"><ArrowIcon /></span></button>)}</div>
    </section>
    <aside className="fidelity-note"><strong>About conversion fidelity</strong><span>PDF is fixed-layout; DOCX, HTML, and Markdown reflow. FileMorph preserves what each target format can represent and reports unsupported files honestly.</span></aside>
  </main>
}
