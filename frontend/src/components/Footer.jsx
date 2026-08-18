import { useUI } from '../context/UIContext.jsx'

export default function Footer() {
  const { toast } = useUI()
  return (
    <footer>
      <div className="foot">
        <div>
          <div className="fbrand">
            <svg width="30" height="30" viewBox="0 0 40 40" fill="none">
              <rect x="1" y="1" width="38" height="38" rx="10" fill="#fff" />
              <path d="M20 6c-5 3-9 4-11 4v9c0 7 5 12 11 15 6-3 11-8 11-15v-9c-2 0-6-1-11-4Z" fill="#b3122a" />
              <path d="M20 12v13M13.5 18.5h13" stroke="#fff" strokeWidth="3" strokeLinecap="round" />
            </svg>
            <b>HealthNexus</b>
          </div>
          <p>A connected healthcare ecosystem for patients, doctors, pharmacies and insurers.</p>
        </div>
        <div>
          <h4>Product</h4>
          <a href="#profile">Patients</a>
          <a href="#doctors">Doctors</a>
          <a href="#pharmacy">Pharmacy</a>
          <a href="#insurance">Insurance</a>
        </div>
        <div>
          <h4>Resources</h4>
          <a href="#insights">Health articles</a>
          <a onClick={(e) => { e.preventDefault(); toast('Support opened') }}>Support</a>
          <a onClick={(e) => { e.preventDefault(); toast('FAQs opened') }}>FAQs</a>
        </div>
        <div>
          <h4>Legal</h4>
          <a onClick={(e) => e.preventDefault()}>Privacy</a>
          <a onClick={(e) => e.preventDefault()}>Terms</a>
          <a onClick={(e) => e.preventDefault()}>Security</a>
          <a onClick={(e) => e.preventDefault()}>Medical disclaimer</a>
        </div>
      </div>
      <div className="copy">© 2026 HealthNexus · Demo prototype with fictional data. Health information shown is educational and not medical advice.</div>
    </footer>
  )
}
