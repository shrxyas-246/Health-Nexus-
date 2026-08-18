import { useState } from 'react'
import { useUI } from '../context/UIContext.jsx'
import { useAuth } from '../context/AuthContext.jsx'
import { useResource } from '../hooks/useResource.js'
import { api } from '../lib/api.js'
import { dayMonth, shortDate, time, titleCase } from '../lib/format.js'
import { Loading, ErrorState, Empty } from '../components/States.jsx'

const FILTERS = [
  { id: '', label: 'Everything' },
  { id: 'consultation', label: 'Consultations' },
  { id: 'prescription', label: 'Prescriptions' },
  { id: 'lab_report', label: 'Lab reports' },
  { id: 'admission', label: 'Admissions' },
  { id: 'surgery', label: 'Surgeries' }
]

export default function History() {
  const { modal, toast } = useUI()
  const { patient } = useAuth()
  const patientId = patient?.id
  const [filter, setFilter] = useState('')

  const { data, loading, error, reload } = useResource(
    () => api.timeline(patientId, { kind: filter || undefined, limit: 100 }),
    [patientId, filter],
    { enabled: Boolean(patientId) }
  )

  const downloadHistory = async () => {
    const events = await api.timeline(patientId, { limit: 300 })
    const text = [
      'HEALTHNEXUS — MEDICAL HISTORY',
      `Patient: ${patient.full_name}   Medical ID: ${patient.medical_id}`,
      '',
      ...events.map((e) =>
        `${shortDate(e.occurred_at)} — ${titleCase(e.kind)} — ${e.title}` +
        (e.summary ? `\n    ${e.summary}` : '') +
        (e.doctor_name ? `\n    Doctor: ${e.doctor_name}` : '') +
        (e.hospital_name ? `\n    Hospital: ${e.hospital_name}` : '')
      )
    ].join('\n')

    const a = document.createElement('a')
    a.href = URL.createObjectURL(new Blob([text], { type: 'text/plain' }))
    a.download = `HealthNexus-History-${patient.medical_id}.txt`
    a.click()
    URL.revokeObjectURL(a.href)
    toast('Medical history downloaded')
  }

  const openEvent = (event) => {
    modal(
      event.title,
      [
        `${titleCase(event.kind)} · ${shortDate(event.occurred_at)} ${time(event.occurred_at)}`,
        event.doctor_name ? `Doctor: ${event.doctor_name}` : '',
        event.hospital_name ? `Hospital: ${event.hospital_name}` : '',
        event.lab_name ? `Lab: ${event.lab_name}` : '',
        '',
        event.summary || 'No further detail recorded.',
        '',
        event.is_legacy ? 'Source: added by you (historical record)' : 'Source: recorded automatically by your care provider'
      ].filter(Boolean).join('\n')
    )
  }

  return (
    <section id="history" data-chapter="Your Records" data-nav="Medical History">
      <div className="section-head reveal">
        <div>
          <div className="eyebrow">Chronological record</div>
          <h2>Your medical journey</h2>
          <p className="muted">
            Every consultation, prescription, report and admission — in the order it happened.
          </p>
        </div>
        <button className="btn" onClick={downloadHistory}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 4v11m0 0 4-4m-4 4-4-4M5 19h14" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          Download history
        </button>
      </div>

      <div className="filters reveal">
        {FILTERS.map((f) => (
          <button
            key={f.id}
            className={`filter${filter === f.id ? ' on' : ''}`}
            onClick={() => setFilter(f.id)}
          >
            {f.label}
          </button>
        ))}
      </div>

      {loading && <Loading label="Loading your timeline…" rows={4} />}
      {error && <ErrorState error={error} onRetry={reload} />}
      {!loading && !error && data?.length === 0 && (
        <Empty title="No records in this view" detail="Try a different filter, or add past records to your timeline." />
      )}

      {!loading && !error && data?.length > 0 && (
        <div className="timeline" id="timeline">
          <div className="rail"><i id="railFill"></i></div>
          <div className="events">
            {data.map((event) => (
              <div className="event" key={event.id}>
                <span className="node"></span>
                <div className="date">
                  <b>{dayMonth(event.occurred_at)}</b>
                  <span>{new Date(event.occurred_at).getFullYear()} · {time(event.occurred_at)}</span>
                </div>
                <div className="record card">
                  <span className="tag">{titleCase(event.kind)}</span>
                  <div className="r-top">
                    <div>
                      <h3>{event.title}</h3>
                      <span className="muted" style={{ fontSize: 12 }}>
                        {[event.hospital_name, event.doctor_name, event.lab_name].filter(Boolean).join(' · ') || 'Your record'}
                      </span>
                    </div>
                    <span className={`badge${event.is_legacy ? '' : ' g'}`}>
                      {event.is_legacy ? 'Added by you' : 'Verified'}
                    </span>
                  </div>
                  {event.summary && (
                    <div className="fields">
                      <div style={{ gridColumn: '1 / -1' }}>
                        <small>Details</small>
                        <b style={{ fontWeight: 500 }}>{event.summary}</b>
                      </div>
                    </div>
                  )}
                  <div className="r-actions">
                    <button className="btn" onClick={() => openEvent(event)}>View full record →</button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  )
}
