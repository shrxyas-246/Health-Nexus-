import { useUI } from '../context/UIContext.jsx'

const Check = () => (
  <span className="check">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
      <path d="m5 12 4 4 10-10" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  </span>
)

export default function Insurance() {
  const { toast, modal } = useUI()
  return (
    <section id="insurance" data-chapter="Billing & Insurance" data-nav="Insurance">
      <div className="section-head reveal">
        <div>
          <div className="eyebrow">Smart claims</div>
          <h2>Insurance without the paperwork.</h2>
          <p className="muted">Verified records help pre-fill eligible claim details. Final approval always stays with the insurer.</p>
        </div>
        <button className="btn red" onClick={() => toast('Claim assistant opened')}>Start a claim</button>
      </div>
      <div className="insurance reveal">
        <div className="ins-card card">
          <div className="ins-head">
            <div><b>Star Health & Allied Insurance</b><span>Corporate health plan · HNX-482913</span></div>
            <span className="badge g">Active</span>
          </div>
          <div className="claim"><Check /><div><b>Verified patient profile</b><span>Identity and contact details</span></div></div>
          <div className="claim"><Check /><div><b>Medical record</b><span>Hospital and doctor information</span></div></div>
          <div className="claim"><Check /><div><b>Prescription & bill</b><span>Linked from HealthNexus</span></div></div>
          <div className="claim"><Check /><div><b>Insurance verification</b><span>Policy information matched</span></div></div>
          <div className="progress">
            <div className="bar"><i data-w="76"></i></div>
            <div className="lbl"><span>Claim preparation</span><span>76%</span></div>
          </div>
        </div>
        <div className="ins-card card">
          <div className="eyebrow">Smart claim assistant</div>
          <h3 style={{ fontSize: 18 }}>Less repeated paperwork.</h3>
          <p className="muted" style={{ marginTop: 8 }}>Your verified records populate eligible fields instead of asking for the same information again and again.</p>
          <div className="insight" style={{ maxWidth: 'none' }}>
            <b>Claim status: Documents verified</b>
            <p>Next step: insurer review</p>
          </div>
          <button
            className="btn red"
            style={{ marginTop: 16 }}
            onClick={() => modal('Claim preview', 'Patient profile ✓\nMedical record ✓\nPrescription ✓\nBill ✓\nInsurance verification ✓\n\nNext step: insurer review')}
          >
            Review claim
          </button>
        </div>
      </div>
    </section>
  )
}
