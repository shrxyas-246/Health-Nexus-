import { useUI } from '../context/UIContext.jsx'

export default function Profile() {
  const { toast, download } = useUI()
  return (
    <section id="profile" data-chapter="Your Records" data-nav="Profile">
      <div className="hero reveal">
        <div>
          <div className="profile card">
            <div className="avatar-xl">
              <span className="init">R</span>
              <span className="ring"></span>
              <span className="verified">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <path d="m5 12 4 4 10-10" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
                Verified
              </span>
            </div>
            <div>
              <div className="eyebrow">Medical ID · HNX-482913</div>
              <h1>Good morning, Rahul.</h1>
              <p className="muted">Your records, prescriptions and health information — connected in one place.</p>
              <div className="chips">
                <div className="chip"><small>Phone</small><b>+91 98765 43210</b></div>
                <div className="chip"><small>Blood group</small><b>O+</b></div>
                <div className="chip"><small>Allergies</small><b>Penicillin</b></div>
                <div className="chip"><small>Last visit</small><b>12 Aug 2026</b></div>
                <div className="chip"><small>Insurance</small><b className="ok">Active</b></div>
              </div>
              <div className="hero-actions">
                <button className="btn red" onClick={() => toast('Profile editor opened')}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M4 20h4L18.5 9.5a2.1 2.1 0 0 0-3-3L5 17v3Z" strokeLinejoin="round" />
                  </svg>
                  Edit profile
                </button>
                <button className="btn" onClick={download}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M12 4v11m0 0 4-4m-4 4-4-4M5 19h14" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                  Download record
                </button>
              </div>
            </div>
          </div>
        </div>
        <aside className="updates card">
          <div className="head">
            <h3 style={{ fontSize: 14 }}>Activity</h3>
            <span className="live"><i className="pulse"></i>Live</span>
          </div>
          <div className="update">
            <span className="u-ico">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M9 3h6l1 2h3v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V5h3l1-2Z" strokeLinejoin="round" />
                <path d="M9 12h6M12 9v6" strokeLinecap="round" />
              </svg>
            </span>
            <div><b>Prescription updated</b><span>Dr. Sharma changed Metformin dosage · 4 min ago</span></div>
          </div>
          <div className="update">
            <span className="u-ico">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M6 3h9l3 3v15H6z" strokeLinejoin="round" />
                <path d="M9 11h6M9 15h4" strokeLinecap="round" />
              </svg>
            </span>
            <div><b>Lab report added</b><span>Blood glucose report is ready · 2 hr ago</span></div>
          </div>
          <div className="update">
            <span className="u-ico">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="8" />
                <path d="M12 8v4l3 2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </span>
            <div><b>Follow-up reminder</b><span>Recommended follow-up in 3 weeks</span></div>
          </div>
          <button
            className="btn"
            style={{ width: '100%', justifyContent: 'center', marginTop: 6 }}
            onClick={() => toast('All notifications opened')}
          >
            View all
          </button>
        </aside>
      </div>
      <div className="metrics reveal">
        <div className="metric"><small>BMI</small><b>23.8</b><span className="tagline ok"><i className="d"></i>Normal</span></div>
        <div className="metric"><small>Fitness</small><b>78</b><span className="tagline ok"><i className="d"></i>Good</span></div>
        <div className="metric"><small>Medicines</small><b>3</b><span className="tagline ok"><i className="d"></i>Current</span></div>
        <div className="metric"><small>Allergies</small><b>2</b><span className="tagline ok"><i className="d"></i>Known</span></div>
        <div className="metric"><small>Last visit</small><b>12 Aug</b><span className="tagline ok"><i className="d"></i>Recorded</span></div>
        <div className="metric"><small>Insurance</small><b>Active</b><span className="tagline ok"><i className="d"></i>Verified</span></div>
      </div>
    </section>
  )
}
