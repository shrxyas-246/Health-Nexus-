import { useUI } from '../context/UIContext.jsx'
import { useAuth } from '../context/AuthContext.jsx'
import { useResource } from '../hooks/useResource.js'
import { api } from '../lib/api.js'
import { relative, shortDate, toneClass } from '../lib/format.js'
import { Loading, ErrorState } from '../components/States.jsx'

const ACTIVITY_ICONS = {
  prescription: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M9 3h6l1 2h3v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V5h3l1-2Z" strokeLinejoin="round" />
      <path d="M9 12h6M12 9v6" strokeLinecap="round" />
    </svg>
  ),
  lab_report: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M6 3h9l3 3v15H6z" strokeLinejoin="round" />
      <path d="M9 11h6M9 15h4" strokeLinecap="round" />
    </svg>
  ),
  default: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="8" />
      <path d="M12 8v4l3 2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

export default function Profile() {
  const { toast, modal } = useUI()
  const { user, logout } = useAuth()
  const { data: summary, loading, error, reload } = useResource(() => api.summary(), [])

  const downloadRecord = async () => {
    const patient = summary.patient
    const [timeline, prescription] = await Promise.all([
      api.timeline(patient.id, { limit: 200 }),
      api.currentPrescription(patient.id)
    ])

    const lines = [
      'HEALTHNEXUS — MEDICAL RECORD',
      `Patient: ${patient.full_name}`,
      `Medical ID: ${patient.medical_id}`,
      `Blood group: ${patient.blood_group || '—'}   BMI: ${patient.bmi ?? '—'}`,
      `Allergies: ${patient.allergies.map((a) => a.substance).join(', ') || 'None recorded'}`,
      '',
      'CURRENT MEDICATION',
      ...(prescription?.items || []).map(
        (i) => `  ${i.medicine_name} ${i.strength || ''} — ${i.dosage || ''} ${i.frequency || ''}`.trim()
      ),
      '',
      'TIMELINE',
      ...timeline.map((e) => `  ${shortDate(e.occurred_at)} — ${e.title}${e.summary ? ` — ${e.summary}` : ''}`)
    ]

    const blob = new Blob([lines.join('\n')], { type: 'text/plain' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `HealthNexus-${patient.medical_id}.txt`
    a.click()
    URL.revokeObjectURL(a.href)
    toast('Medical record downloaded')
  }

  if (loading) {
    return <section id="profile" data-chapter="Your Records" data-nav="Profile"><Loading label="Loading your record…" rows={5} /></section>
  }
  if (error) {
    return <section id="profile" data-chapter="Your Records" data-nav="Profile"><ErrorState error={error} onRetry={reload} /></section>
  }

  const { patient, metrics, activity } = summary
  const firstName = patient.full_name.split(' ')[0]
  const hour = new Date().getHours()
  const greeting = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening'

  return (
    <section id="profile" data-chapter="Your Records" data-nav="Profile">
      <div className="hero reveal">
        <div>
          <div className="profile card">
            <div className="avatar-xl">
              <span className="init">{firstName[0]}</span>
              <span className="ring"></span>
              {patient.is_verified && (
                <span className="verified">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                    <path d="m5 12 4 4 10-10" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                  Verified
                </span>
              )}
            </div>
            <div>
              <div className="eyebrow">Medical ID · {patient.medical_id}</div>
              <h1>{greeting}, {firstName}.</h1>
              <p className="muted">Your records, prescriptions and health information — connected in one place.</p>
              <div className="chips">
                <div className="chip"><small>Phone</small><b>{patient.phone || '—'}</b></div>
                <div className="chip"><small>Blood group</small><b>{patient.blood_group || '—'}</b></div>
                <div className="chip">
                  <small>Allergies</small>
                  <b>{patient.allergies.map((a) => a.substance).join(', ') || 'None'}</b>
                </div>
                <div className="chip"><small>Age</small><b>{patient.age ?? '—'}</b></div>
                <div className="chip">
                  <small>Insurance</small>
                  <b className={summary.insurance_status === 'Active' ? 'ok' : ''}>{summary.insurance_status}</b>
                </div>
              </div>
              <div className="hero-actions">
                <button
                  className="btn red"
                  onClick={() => modal(
                    'Your profile',
                    [
                      `Name: ${patient.full_name}`,
                      `Medical ID: ${patient.medical_id}`,
                      `Date of birth: ${shortDate(patient.date_of_birth)}`,
                      `Gender: ${patient.gender || '—'}`,
                      `Blood group: ${patient.blood_group || '—'}`,
                      `Height: ${patient.height_cm ?? '—'} cm   Weight: ${patient.weight_kg ?? '—'} kg`,
                      `BMI: ${patient.bmi ?? '—'}`,
                      `Address: ${patient.address || '—'}`,
                      '',
                      `Emergency contact: ${patient.emergency_contact_name || '—'} ${patient.emergency_contact_phone || ''}`
                    ].join('\n')
                  )}
                >
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M4 20h4L18.5 9.5a2.1 2.1 0 0 0-3-3L5 17v3Z" strokeLinejoin="round" />
                  </svg>
                  View profile
                </button>
                <button className="btn" onClick={downloadRecord}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M12 4v11m0 0 4-4m-4 4-4-4M5 19h14" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                  Download record
                </button>
                <button className="btn" onClick={logout} title={user?.email}>Sign out</button>
              </div>
            </div>
          </div>
        </div>
        <aside className="updates card">
          <div className="head">
            <h3 style={{ fontSize: 14 }}>Activity</h3>
            <span className="live"><i className="pulse"></i>Live</span>
          </div>
          {activity.length === 0 && <p className="muted" style={{ fontSize: 13 }}>No activity recorded yet.</p>}
          {activity.slice(0, 4).map((item, i) => (
            <div className="update" key={i}>
              <span className="u-ico">{ACTIVITY_ICONS[item.kind] || ACTIVITY_ICONS.default}</span>
              <div>
                <b>{item.title}</b>
                <span>{[item.detail, relative(item.at)].filter(Boolean).join(' · ')}</span>
              </div>
            </div>
          ))}
          <button
            className="btn"
            style={{ width: '100%', justifyContent: 'center', marginTop: 6 }}
            onClick={() => modal(
              'Full activity',
              activity.map((a) => `${shortDate(a.at)} — ${a.title}${a.detail ? `\n    ${a.detail}` : ''}`).join('\n\n')
            )}
          >
            View all
          </button>
        </aside>
      </div>
      <div className="metrics reveal">
        {metrics.map((m) => (
          <div className="metric" key={m.key}>
            <small>{m.label}</small>
            <b>{m.value}</b>
            <span className={`tagline ${toneClass(m.tone)}`}><i className="d"></i>{m.tag}</span>
          </div>
        ))}
      </div>
    </section>
  )
}
