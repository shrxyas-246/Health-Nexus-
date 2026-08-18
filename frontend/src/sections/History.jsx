import { useUI } from '../context/UIContext.jsx'

export default function History() {
  const { modal, download } = useUI()
  return (
    <section id="history" data-chapter="Your Records" data-nav="Medical History">
      <div className="section-head reveal">
        <div>
          <div className="eyebrow">Chronological record</div>
          <h2>Your medical journey</h2>
          <p className="muted">The line draws itself as you scroll, revealing each record in order so the story stays easy to follow.</p>
        </div>
        <button className="btn" onClick={download}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 4v11m0 0 4-4m-4 4-4-4M5 19h14" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          Download history
        </button>
      </div>
      <div className="timeline" id="timeline">
        <div className="rail"><i id="railFill"></i></div>
        <div className="events">
          <div className="event">
            <span className="node"></span>
            <div className="date"><b>18 AUG 2026</b><span>10:26 AM</span></div>
            <div className="record card">
              <span className="tag">DOCTOR CONSULTATION</span>
              <div className="r-top">
                <div><h3>Dr. Ananya Sharma</h3><span className="muted" style={{ fontSize: 12 }}>Apollo Healthcare · General Medicine</span></div>
                <span className="badge g">Updated</span>
              </div>
              <div className="fields">
                <div><small>Diagnosis</small><b>Blood pressure review</b></div>
                <div><small>Medication</small><b>Prescription updated</b></div>
                <div><small>Follow-up</small><b>In 3 weeks</b></div>
              </div>
              <div className="r-actions">
                <button className="btn" onClick={() => modal('Doctor consultation', 'Dr. Ananya Sharma · Apollo Healthcare\n\nDiagnosis: Blood pressure review\nPrescription updated\nFollow-up: 3 weeks')}>
                  View full record →
                </button>
              </div>
            </div>
          </div>
          <div className="event">
            <span className="node"></span>
            <div className="date"><b>16 AUG 2026</b><span>11:17 AM</span></div>
            <div className="record card">
              <span className="tag">LABORATORY</span>
              <div className="r-top">
                <div><h3>Blood test results</h3><span className="muted" style={{ fontSize: 12 }}>LabCare Diagnostics</span></div>
                <span className="badge g">Verified</span>
              </div>
              <div className="fields">
                <div><small>HbA1c</small><b>5.8%</b></div>
                <div><small>Glucose</small><b>102 mg/dL</b></div>
                <div><small>Report</small><b>Available</b></div>
              </div>
              <div className="r-actions">
                <button className="btn" onClick={() => modal('Blood test results', 'LabCare Diagnostics · 16 Aug 2026\n\nHbA1c: 5.8%\nFasting glucose: 102 mg/dL\nStatus: Within range')}>
                  View full record →
                </button>
              </div>
            </div>
          </div>
          <div className="event">
            <span className="node"></span>
            <div className="date"><b>20 AUG 2025</b><span>09:50 PM</span></div>
            <div className="record card">
              <span className="tag">HOSPITAL ADMISSION</span>
              <div className="r-top">
                <div><h3>General ward admission</h3><span className="muted" style={{ fontSize: 12 }}>Apollo Healthcare</span></div>
                <span className="badge g">Completed</span>
              </div>
              <div className="fields">
                <div><small>Admitted</small><b>20 Aug · 9:50 PM</b></div>
                <div><small>Discharged</small><b>23 Aug · 4:15 PM</b></div>
                <div><small>Document</small><b>Discharge summary</b></div>
              </div>
              <div className="r-actions">
                <button className="btn" onClick={() => modal('Hospital admission', 'Apollo Healthcare\n\nAdmitted: 20 Aug 2025 · 9:50 PM\nDischarged: 23 Aug 2025 · 4:15 PM\nDocument: Discharge summary available')}>
                  View full record →
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
