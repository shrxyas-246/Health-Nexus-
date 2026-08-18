import { useUI } from '../context/UIContext.jsx'

const links = [
  { id: 'profile', label: 'Profile' },
  { id: 'prescriptions', label: 'Prescriptions' },
  { id: 'history', label: 'Records' },
  { id: 'billing', label: 'Billing' },
  { id: 'insurance', label: 'Insurance' },
  { id: 'doctors', label: 'Doctors' },
  { id: 'pharmacy', label: 'Pharmacy' },
  { id: 'insights', label: 'Insights' }
]

export default function TopNav({ activeId }) {
  const { toast } = useUI()
  return (
    <header className="top">
      <div className="nav">
        <a className="brand" href="#profile">
          <svg className="mark" viewBox="0 0 40 40" fill="none" aria-hidden="true">
            <rect x="1" y="1" width="38" height="38" rx="10" fill="#fff" />
            <path d="M20 6c-5 3-9 4-11 4v9c0 7 5 12 11 15 6-3 11-8 11-15v-9c-2 0-6-1-11-4Z" fill="#b3122a" />
            <path d="M20 12v13M13.5 18.5h13" stroke="#fff" strokeWidth="3" strokeLinecap="round" />
          </svg>
          <span className="wm"><b>HealthNexus</b><small>Patient</small></span>
        </a>
        <nav className="links">
          {links.map((l) => (
            <a
              key={l.id}
              href={`#${l.id}`}
              data-id={l.id}
              className={activeId === l.id ? 'active' : ''}
            >
              {l.label}
            </a>
          ))}
        </nav>
        <div className="right">
          <button className="ico-btn" title="Search" onClick={() => toast('Search opened')} aria-label="Search">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
              <circle cx="11" cy="11" r="7" /><path d="m20 20-3-3" strokeLinecap="round" />
            </svg>
          </button>
          <button className="ico-btn" title="Notifications" onClick={() => toast('3 new notifications')} aria-label="Notifications">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
              <path d="M18 8a6 6 0 1 0-12 0c0 7-3 8-3 8h18s-3-1-3-8" strokeLinecap="round" strokeLinejoin="round" />
              <path d="M13.7 21a2 2 0 0 1-3.4 0" strokeLinecap="round" />
            </svg>
          </button>
          <button className="sub" onClick={() => toast('HealthNexus Plus checkout opened')}>Subscribe</button>
          <div className="me" title="Rahul Verma">RV</div>
        </div>
      </div>
    </header>
  )
}
