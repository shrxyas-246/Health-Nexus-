import { useUI } from '../context/UIContext.jsx'

export default function Insights() {
  const { toast } = useUI()
  return (
    <section id="insights" data-chapter="Care & Insights" data-nav="Insights">
      <div className="section-head reveal">
        <div>
          <div className="eyebrow">Health updates & insights</div>
          <h2>Useful reading, without the clutter.</h2>
        </div>
        <a className="view" href="#insights">View all →</a>
      </div>
      <div className="feature reveal">
        <div className="thumb th-card">
          <svg className="deco" viewBox="0 0 400 230" preserveAspectRatio="none">
            <path d="M0 150 L60 150 L80 110 L100 175 L120 90 L145 150 L400 150" fill="none" stroke="rgba(255,255,255,.5)" strokeWidth="3" strokeLinejoin="round" />
          </svg>
          <span className="cat">Featured · Cardiology</span>
        </div>
        <div>
          <h2>Understanding your blood pressure: what your numbers mean</h2>
          <p className="muted">A patient-friendly guide to systolic and diastolic readings, what the trends mean, and useful questions to discuss with your clinician.</p>
          <a className="view" href="#insights" onClick={(e) => { e.preventDefault(); toast('Article opened') }}>Read article →</a>
        </div>
      </div>
      <div className="stories reveal">
        <article className="story">
          <div className="thumb th-lab"><span className="cat">Laboratory</span></div>
          <div className="body"><h3>5 things to know before your next blood test</h3><div className="meta3">3 min read</div></div>
        </article>
        <article className="story">
          <div className="thumb th-med"><span className="cat">Medication</span></div>
          <div className="body"><h3>Understanding medication dosage & timing</h3><div className="meta3">4 min read</div></div>
        </article>
        <article className="story">
          <div className="thumb th-well"><span className="cat">Wellness</span></div>
          <div className="body"><h3>How preventive health checks can help</h3><div className="meta3">5 min read</div></div>
        </article>
      </div>
    </section>
  )
}
