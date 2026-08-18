import { useState } from 'react'
import { useUI } from '../context/UIContext.jsx'
import { useAuth } from '../context/AuthContext.jsx'
import { useResource } from '../hooks/useResource.js'
import { api } from '../lib/api.js'
import { money } from '../lib/format.js'
import { Loading, ErrorState, Empty } from '../components/States.jsx'

export default function Pharmacy() {
  const { toast, modal } = useUI()
  const { patient } = useAuth()
  const [busy, setBusy] = useState(null)

  const { data, loading, error, reload } = useResource(
    async () => {
      const prescription = await api.currentPrescription(patient.id)
      if (patient.is_premium) {
        try {
          const ranked = await api.recommendedPharmacies({ limit: 4 })
          if (ranked.length) return { pharmacies: ranked, ranked: true, prescription }
        } catch {
          /* fall through to the plain directory */
        }
      }
      return { pharmacies: await api.pharmacies({ limit: 4 }), ranked: false, prescription }
    },
    [patient?.id, patient?.is_premium],
    { enabled: Boolean(patient) }
  )

  const order = async (pharmacy) => {
    if (!data.prescription) return toast('You have no active prescription to send')
    setBusy(pharmacy.id)
    try {
      const placed = await api.placeMedicineOrder({
        pharmacy_id: pharmacy.id,
        prescription_id: data.prescription.id,
        delivery: pharmacy.delivers
      })
      toast(`Order placed at ${pharmacy.name} · ${money(placed.total_amount)}`)
    } catch (err) {
      toast(err.detail || 'Could not place the order')
    } finally {
      setBusy(null)
    }
  }

  const emergency = async () => {
    if (!window.confirm('Dispatch an ambulance from the nearest hospital and send your record ahead?')) return
    try {
      const request = await api.triggerEmergency({ complaint: 'Emergency requested from the app' })
      modal(
        'Ambulance dispatched',
        [
          `Hospital: ${request.hospital_name}`,
          `Phone: ${request.hospital_phone || '—'}`,
          `Ambulance: ${request.ambulance_ref}`,
          `ETA: ${request.ambulance_eta_minutes} minutes`,
          '',
          'Your full medical record has been sent to the hospital.',
          'Registration paperwork is deferred until after you arrive.'
        ].join('\n')
      )
    } catch (err) {
      toast(err.detail || 'Could not raise the emergency request')
    }
  }

  const body = () => {
    if (loading) return <Loading label="Finding pharmacies…" rows={3} />
    if (error) return <ErrorState error={error} onRetry={reload} />
    if (!data.pharmacies.length) return <Empty title="No partner pharmacies yet" />

    return (
      <div className="pharm reveal">
        {data.pharmacies.map((p) => (
          <div className="pcard card hoverable" key={p.id}>
            <div className="p-top">
              <h3>{p.name}</h3>
              <span className="open">{p.is_24x7 ? 'Open 24×7' : 'Open'}</span>
            </div>
            <div className="meta2">
              {[
                p.distance_km != null ? `${p.distance_km} km` : p.city,
                p.delivers ? `${p.avg_delivery_minutes} min delivery` : 'Counter pickup'
              ].filter(Boolean).join(' · ')}
            </div>
            <div className="disc">
              {p.quoted_total != null
                ? `Your prescription: ${money(p.quoted_total)}`
                : `★ ${p.rating_avg || '—'} · ${p.rating_count} reviews`}
            </div>
            {data.ranked && p.match_reason && <div className="match-why light">{p.match_reason}</div>}
            {p.unavailable_items?.length > 0 && (
              <div className="warn-line">Out of stock: {p.unavailable_items.join(', ')}</div>
            )}
            <button
              className="btn red"
              disabled={busy === p.id || !data.prescription}
              onClick={() => order(p)}
            >
              {busy === p.id ? 'Ordering…' : data.prescription ? 'Send prescription' : 'No prescription'}
            </button>
          </div>
        ))}

        <div className="pcard card emergency">
          <div className="s-ico">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 3v18M3 12h18" strokeLinecap="round" />
            </svg>
          </div>
          <h3>Emergency assistance</h3>
          <p>One tap books an ambulance from the nearest hospital and sends your record ahead — paperwork waits.</p>
          <button className="btn" onClick={emergency}>Need help now?</button>
        </div>
      </div>
    )
  }

  return (
    <section id="pharmacy" data-chapter="Care & Insights" data-nav="Pharmacy">
      <div className="section-head reveal">
        <div>
          <div className="eyebrow">{data?.ranked ? 'Priced for your prescription' : 'Partner pharmacies'}</div>
          <h2>Medicines, delivered.</h2>
          <p className="muted">
            {data?.ranked
              ? 'Each store priced against the medicines you are actually taking.'
              : 'Forward your prescription to a nearby pharmacy and collect or have it delivered.'}
          </p>
        </div>
      </div>
      {body()}
    </section>
  )
}
