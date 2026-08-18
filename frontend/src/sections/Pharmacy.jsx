import { useUI } from '../context/UIContext.jsx'

const pharmacies = [
  { name: 'HealthPlus Pharmacy', meta: '1.2 km · 30–45 min delivery', disc: '10% HealthNexus discount' },
  { name: 'MediCare Corner', meta: '2.1 km · 45–60 min delivery', disc: '8% HealthNexus discount' },
  { name: 'WellCare Pharmacy', meta: '3.4 km · 60 min delivery', disc: '5% HealthNexus discount' }
]

export default function Pharmacy() {
  const { toast } = useUI()
  return (
    <section id="pharmacy" data-chapter="Care & Insights" data-nav="Pharmacy">
      <div className="section-head reveal">
        <div>
          <div className="eyebrow">Partner pharmacies</div>
          <h2>Medicines, delivered.</h2>
          <p className="muted">Connect your prescriptions with nearby pharmacy partners and available discounts.</p>
        </div>
        <a className="view" href="#pharmacy">View nearby →</a>
      </div>
      <div className="pharm reveal">
        {pharmacies.map((p) => (
          <div className="pcard card hoverable" key={p.name}>
            <div className="p-top"><h3>{p.name}</h3><span className="open">Open</span></div>
            <div className="meta2">{p.meta}</div>
            <div className="disc">{p.disc}</div>
            <button className="btn red" onClick={() => toast('Prescription required to order')}>View medicines</button>
          </div>
        ))}
        <div className="pcard card emergency">
          <div className="s-ico">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 3v18M3 12h18" strokeLinecap="round" />
            </svg>
          </div>
          <h3>Emergency assistance</h3>
          <p>Request an ambulance, call emergency services or share your medical profile instantly.</p>
          <button className="btn" onClick={() => toast('Emergency service demo opened')}>Need help now?</button>
        </div>
      </div>
    </section>
  )
}
