import { useUI } from '../context/UIContext.jsx'

export default function Plus() {
  const { toast } = useUI()
  return (
    <section id="plus" data-chapter="Care & Insights" data-nav="Plus" style={{ borderBottom: 0 }}>
      <div className="plus reveal">
        <div>
          <div className="eyebrow">HealthNexus Plus</div>
          <h2>Your health. One connected journey.</h2>
          <p>Medical records, prescriptions, doctors, insurance, pharmacy and health insights — together in one place.</p>
        </div>
        <div className="price">
          <b>₹199</b><span className="per"> / month</span>
          <div>
            <button className="btn red" style={{ marginTop: 12 }} onClick={() => toast('HealthNexus Plus checkout opened')}>
              Subscribe now
            </button>
          </div>
        </div>
      </div>
    </section>
  )
}
