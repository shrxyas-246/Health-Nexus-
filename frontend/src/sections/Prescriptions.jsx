import { useUI } from '../context/UIContext.jsx'

const PillIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <rect x="3" y="8" width="18" height="8" rx="4" /><path d="M12 8v8" />
  </svg>
)
const PlusIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <circle cx="12" cy="12" r="8" /><path d="M12 8v8M8 12h8" strokeLinecap="round" />
  </svg>
)

export default function Prescriptions() {
  const { modal, download } = useUI()
  return (
    <section id="prescriptions" data-chapter="Your Records" data-nav="Prescriptions">
      <div className="section-head reveal">
        <div>
          <div className="eyebrow">Prescription archive</div>
          <h2>Your prescriptions</h2>
          <p className="muted">Every update keeps its previous version, doctor and timestamp — nothing is silently overwritten.</p>
        </div>
        <a className="view" href="#prescriptions">View all →</a>
      </div>
      <div className="rx reveal">
        <div className="rxcard card">
          <div className="doctor">
            <div className="avatar av1" style={{ width: 46, height: 46, fontSize: 15 }}>AS</div>
            <div>
              <b>Dr. Ananya Sharma</b>
              <span className="muted" style={{ fontSize: 12 }}>General Medicine · 18 Aug 2026 · 10:26 AM</span>
            </div>
            <span className="status badge g">Updated</span>
          </div>
          <div className="med">
            <div className="name">
              <span className="pill"><PillIcon /></span>
              <div><b>Metformin 850 mg</b><span className="sub2">Type 2 diabetes support</span></div>
            </div>
            <div className="dose">1 tablet · twice daily</div>
            <div className="days">30 days</div>
          </div>
          <div className="med">
            <div className="name">
              <span className="pill"><PlusIcon /></span>
              <div><b>Vitamin D3</b><span className="sub2">Supplement</span></div>
            </div>
            <div className="dose">1 capsule · daily</div>
            <div className="days">30 days</div>
          </div>
          <div className="med" style={{ borderBottom: 0 }}>
            <div className="name">
              <span className="pill"><PillIcon /></span>
              <div><b>Atorvastatin 10 mg</b><span className="sub2">Cholesterol management</span></div>
            </div>
            <div className="dose">1 tablet · nightly</div>
            <div className="days">30 days</div>
          </div>
          <div className="rx-actions">
            <button
              className="btn red"
              onClick={() => modal(
                'Prescription — 18 Aug 2026',
                'Dr. Ananya Sharma\n18 Aug 2026 · 10:26 AM\n\nMetformin 850 mg — twice daily — 30 days\nVitamin D3 — daily — 30 days\nAtorvastatin 10 mg — nightly — 30 days'
              )}
            >
              View prescription
            </button>
            <button className="btn" onClick={download}>Download PDF</button>
          </div>
        </div>
        <div className="version card">
          <div className="eyebrow">Version history</div>
          <div className="v"><span className="vdot"></span><div><b>V2 · 18 Aug 2026</b><span>Metformin increased to 850 mg by Dr. Sharma</span></div></div>
          <div className="v old"><span className="vdot"></span><div><b>V1 · 12 Aug 2026</b><span>Initial prescription created</span></div></div>
          <div className="insight" style={{ marginTop: 16, maxWidth: 'none' }}>
            <p style={{ margin: 0 }}>Previous versions stay visible so you and your doctor always see the full history.</p>
          </div>
        </div>
      </div>
    </section>
  )
}
