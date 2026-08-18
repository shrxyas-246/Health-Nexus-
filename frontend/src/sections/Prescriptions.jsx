import { useState } from 'react'
import { useUI } from '../context/UIContext.jsx'
import { useAuth } from '../context/AuthContext.jsx'
import { useResource } from '../hooks/useResource.js'
import { api } from '../lib/api.js'
import { money, shortDate, time } from '../lib/format.js'
import { Loading, ErrorState, Empty } from '../components/States.jsx'

const PillIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <rect x="3" y="8" width="18" height="8" rx="4" /><path d="M12 8v8" />
  </svg>
)

export default function Prescriptions() {
  const { modal, toast } = useUI()
  const { patient } = useAuth()
  const patientId = patient?.id
  const [ordering, setOrdering] = useState(false)

  const { data, loading, error, reload } = useResource(
    async () => {
      const current = await api.currentPrescription(patientId)
      if (!current) return { current: null, versions: [], pharmacies: [] }
      const [versions, pharmacies] = await Promise.all([
        api.prescriptionVersions(current.id),
        api.pharmacies({ limit: 5 })
      ])
      return { current, versions, pharmacies }
    },
    [patientId],
    { enabled: Boolean(patientId) }
  )

  const forwardToPharmacy = async (pharmacyId, name) => {
    setOrdering(true)
    try {
      const order = await api.placeMedicineOrder({
        pharmacy_id: pharmacyId,
        prescription_id: data.current.id,
        delivery: true
      })
      toast(`Order sent to ${name} · ${money(order.total_amount)}`)
    } catch (err) {
      toast(err.detail || 'Could not place the order')
    } finally {
      setOrdering(false)
    }
  }

  const showPrescription = () => {
    const rx = data.current
    modal(
      `Prescription — ${shortDate(rx.issued_at)}`,
      [
        `${rx.doctor_name || 'Doctor'}${rx.doctor_specialization ? ` · ${rx.doctor_specialization}` : ''}`,
        `${shortDate(rx.issued_at)} · ${time(rx.issued_at)} · Version ${rx.version}`,
        rx.diagnosis_summary ? `\nDiagnosis: ${rx.diagnosis_summary}` : '',
        '',
        ...rx.items.map((i) =>
          `${i.medicine_name} ${i.strength || ''} — ${[i.dosage, i.frequency, i.timing].filter(Boolean).join(' · ')}` +
          (i.duration_days ? ` — ${i.duration_days} days` : '')
        ),
        rx.test_requests.length ? `\nTests requested:\n${rx.test_requests.map((t) => `  • ${t.test_name}${t.reason ? ` (${t.reason})` : ''}`).join('\n')}` : '',
        rx.diet_advice ? `\nDiet advice:\n${rx.diet_advice}` : '',
        rx.lifestyle_advice ? `\nLifestyle advice:\n${rx.lifestyle_advice}` : ''
      ].filter(Boolean).join('\n')
    )
  }

  const body = () => {
    if (loading) return <Loading label="Loading your prescriptions…" rows={4} />
    if (error) return <ErrorState error={error} onRetry={reload} />
    if (!data.current) {
      return <Empty title="No active prescription" detail="Prescriptions your doctor writes will appear here." />
    }

    const rx = data.current
    return (
      <div className="rx reveal">
        <div className="rxcard card">
          <div className="doctor">
            <div className="avatar av1" style={{ width: 46, height: 46, fontSize: 15 }}>
              {(rx.doctor_name || 'Dr').split(' ').slice(-2).map((w) => w[0]).join('').slice(0, 2)}
            </div>
            <div>
              <b>{rx.doctor_name || 'Your doctor'}</b>
              <span className="muted" style={{ fontSize: 12 }}>
                {[rx.doctor_specialization, shortDate(rx.issued_at), time(rx.issued_at)].filter(Boolean).join(' · ')}
              </span>
            </div>
            <span className="status badge g">{rx.version > 1 ? `Version ${rx.version}` : 'Current'}</span>
          </div>

          {rx.items.map((item) => (
            <div className="med" key={item.id}>
              <div className="name">
                <span className="pill"><PillIcon /></span>
                <div>
                  <b>{item.medicine_name}{item.strength ? ` ${item.strength}` : ''}</b>
                  <span className="sub2">{item.purpose || item.form || 'Medication'}</span>
                </div>
              </div>
              <div className="dose">{[item.dosage, item.frequency].filter(Boolean).join(' · ') || '—'}</div>
              <div className="days">{item.duration_days ? `${item.duration_days} days` : '—'}</div>
            </div>
          ))}

          {rx.test_requests.length > 0 && (
            <div className="rx-tests">
              <div className="eyebrow">Tests requested</div>
              {rx.test_requests.map((t) => (
                <div className="rx-test" key={t.id}>
                  <b>{t.test_name}</b>
                  <span className={`badge ${t.fulfilled ? 'g' : ''}`}>{t.fulfilled ? 'Booked' : 'Pending'}</span>
                </div>
              ))}
            </div>
          )}

          <div className="rx-actions">
            <button className="btn red" onClick={showPrescription}>View prescription</button>
            {data.pharmacies[0] && (
              <button
                className="btn"
                disabled={ordering}
                onClick={() => forwardToPharmacy(data.pharmacies[0].id, data.pharmacies[0].name)}
              >
                {ordering ? 'Sending…' : `Send to ${data.pharmacies[0].name}`}
              </button>
            )}
          </div>
        </div>

        <div className="version card">
          <div className="eyebrow">Version history</div>
          {data.versions.map((v, i) => (
            <div className={`v${i === 0 ? '' : ' old'}`} key={v.id}>
              <span className="vdot"></span>
              <div>
                <b>V{v.version} · {shortDate(v.issued_at)}</b>
                <span>{v.change_note || (v.version === 1 ? 'Initial prescription created' : 'Updated')}</span>
              </div>
            </div>
          ))}
          {(rx.diet_advice || rx.lifestyle_advice) && (
            <div className="insight" style={{ marginTop: 16, maxWidth: 'none' }}>
              <b>Advice from {rx.doctor_name || 'your doctor'}</b>
              <p style={{ margin: '6px 0 0' }}>{rx.diet_advice || rx.lifestyle_advice}</p>
            </div>
          )}
        </div>
      </div>
    )
  }

  return (
    <section id="prescriptions" data-chapter="Your Records" data-nav="Prescriptions">
      <div className="section-head reveal">
        <div>
          <div className="eyebrow">Prescription archive</div>
          <h2>Your prescriptions</h2>
          <p className="muted">
            Every update keeps its previous version, doctor and timestamp — nothing is silently overwritten.
          </p>
        </div>
      </div>
      {body()}
    </section>
  )
}
