import { useState } from 'react'
import { useUI } from '../context/UIContext.jsx'
import { useAuth } from '../context/AuthContext.jsx'
import { useResource } from '../hooks/useResource.js'
import { api } from '../lib/api.js'
import { money } from '../lib/format.js'
import { Loading, ErrorState, Empty } from '../components/States.jsx'

const AVATARS = ['av1', 'av2', 'av3']
const initials = (name) =>
  (name || '').split(' ').filter((w) => !w.endsWith('.')).slice(0, 2).map((w) => w[0]).join('').toUpperCase()

/* Next free slot: tomorrow at 11:00 local, sent to the API as UTC. */
const nextSlot = () => {
  const d = new Date()
  d.setDate(d.getDate() + 1)
  d.setHours(11, 0, 0, 0)
  return d
}

export default function Doctors() {
  const { toast, modal } = useUI()
  const { patient } = useAuth()
  const [booking, setBooking] = useState(null)

  const { data, loading, error, reload } = useResource(
    async () => {
      // Premium users get the ranked list; everyone else gets the directory.
      if (patient?.is_premium) {
        try {
          const ranked = await api.recommendedDoctors({ limit: 6 })
          if (ranked.length) return { doctors: ranked, ranked: true }
        } catch {
          /* fall through to the plain directory */
        }
      }
      return { doctors: await api.doctors({ limit: 6 }), ranked: false }
    },
    [patient?.is_premium],
    { enabled: Boolean(patient) }
  )

  const book = async (doctor) => {
    setBooking(doctor.id)
    try {
      const appointment = await api.bookAppointment({
        doctor_id: doctor.id,
        scheduled_at: nextSlot().toISOString(),
        reason: 'Consultation booked from HealthNexus'
      })
      toast(`Booked with ${doctor.full_name} · ${money(appointment.fee)}`)
    } catch (err) {
      toast(err.detail || 'Could not book this slot')
    } finally {
      setBooking(null)
    }
  }

  const openProfile = async (doctor) => {
    const reviews = await api.reviews('doctor', doctor.id).catch(() => [])
    modal(
      doctor.full_name,
      [
        `${doctor.specialization}${doctor.qualifications ? ` · ${doctor.qualifications}` : ''}`,
        doctor.hospital_name ? `${doctor.hospital_name}` : '',
        `${doctor.years_experience} years experience · Consultation ${money(doctor.consultation_fee)}`,
        `Rating: ${doctor.rating_avg || '—'} (${doctor.rating_count} review${doctor.rating_count === 1 ? '' : 's'})`,
        doctor.complex_case_success_rate ? `Complex case success rate: ${doctor.complex_case_success_rate}%` : '',
        doctor.languages ? `Speaks: ${doctor.languages}` : '',
        doctor.match_reason ? `\nWhy this match: ${doctor.match_reason}` : '',
        doctor.bio ? `\n${doctor.bio}` : '',
        reviews.length ? `\n\nPatient reviews\n${reviews.map((r) => `  ${'★'.repeat(r.rating)} ${r.title || ''}\n    "${r.comment}" — ${r.author_name}`).join('\n\n')}` : ''
      ].filter(Boolean).join('\n')
    )
  }

  const body = () => {
    if (loading) return <Loading label="Finding doctors…" rows={3} />
    if (error) return <ErrorState error={error} onRetry={reload} />
    if (!data.doctors.length) return <Empty title="No doctors listed yet" />

    return (
      <div className="doctors">
        {data.doctors.map((d, i) => (
          <div className="doccard" key={d.id}>
            <div className="d-top">
              <div className={`avatar ${AVATARS[i % AVATARS.length]}`} style={{ width: 46, height: 46, fontSize: 15 }}>
                {initials(d.full_name)}
              </div>
              <div>
                <h3>{d.full_name}</h3>
                <span className="spec">{d.specialization} · {d.years_experience} yrs</span>
              </div>
            </div>
            <div className="rate">
              ★ {d.rating_avg || '—'}
              <span className="slot">
                {' · '}{money(d.consultation_fee)}
                {d.distance_km != null ? ` · ${d.distance_km} km` : ''}
              </span>
            </div>
            {data.ranked && d.match_reason && <div className="match-why">{d.match_reason}</div>}
            <div className="doc-actions">
              <button className="btn ghost-d" disabled={booking === d.id} onClick={() => book(d)}>
                {booking === d.id ? 'Booking…' : 'Book consultation'}
              </button>
              <button className="btn ghost-d" onClick={() => openProfile(d)}>Profile</button>
            </div>
          </div>
        ))}
      </div>
    )
  }

  return (
    <section id="doctors" data-chapter="Care & Insights" data-nav="Doctors" style={{ borderBottom: 0, paddingBottom: 0 }}>
      <div className="dark reveal">
        <div className="section-head" style={{ marginBottom: 0 }}>
          <div>
            <div className="eyebrow">{data?.ranked ? 'Matched to your conditions' : 'Doctor connect'}</div>
            <h2>Find the right doctor.</h2>
            <p className="muted">
              {data?.ranked
                ? 'Ranked for your active conditions, outcomes and distance.'
                : 'Search specialists, compare availability and book consultations.'}
            </p>
          </div>
        </div>
        {body()}
      </div>
    </section>
  )
}
