import { useUI } from '../context/UIContext.jsx'

const doctors = [
  { avatar: 'av1', initials: 'AS', name: 'Dr. Ananya Sharma', spec: 'General Medicine · 9 yrs', rate: '★ 4.9', slot: 'Today 5:30 PM' },
  { avatar: 'av2', initials: 'RM', name: 'Dr. Rahul Mehta', spec: 'Dermatology · 12 yrs', rate: '★ 4.8', slot: 'Tomorrow 11 AM' },
  { avatar: 'av3', initials: 'PN', name: 'Dr. Priya Nair', spec: 'Nutrition · 8 yrs', rate: '★ 4.9', slot: 'Video available' }
]

export default function Doctors() {
  const { toast } = useUI()
  return (
    <section id="doctors" data-chapter="Care & Insights" data-nav="Doctors" style={{ borderBottom: 0, paddingBottom: 0 }}>
      <div className="dark reveal">
        <div className="section-head" style={{ marginBottom: 0 }}>
          <div>
            <div className="eyebrow">Doctor connect</div>
            <h2>Find the right doctor.</h2>
            <p className="muted">Search specialists, compare availability and book consultations.</p>
          </div>
          <a className="view" href="#doctors">View all →</a>
        </div>
        <div className="doctors">
          {doctors.map((d) => (
            <div className="doccard" key={d.name}>
              <div className="d-top">
                <div className={`avatar ${d.avatar}`} style={{ width: 46, height: 46, fontSize: 15 }}>{d.initials}</div>
                <div><h3>{d.name}</h3><span className="spec">{d.spec}</span></div>
              </div>
              <div className="rate">{d.rate} <span className="slot">· {d.slot}</span></div>
              <button className="btn ghost-d" onClick={() => toast(`Booking opened for ${d.name}`)}>
                Book consultation
              </button>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
