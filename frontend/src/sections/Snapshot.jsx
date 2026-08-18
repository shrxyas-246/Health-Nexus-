import { useAuth } from '../context/AuthContext.jsx'
import { useResource } from '../hooks/useResource.js'
import { api } from '../lib/api.js'
import { Loading, ErrorState } from '../components/States.jsx'

const CHARTS = [
  { kind: 'weight', label: 'Weight trend', unit: 'kg', better: 'down' },
  { kind: 'hba1c', label: 'HbA1c', unit: '%', better: 'down' },
  { kind: 'bp_systolic', label: 'Blood pressure', unit: 'mmHg', better: 'down' },
  { kind: 'glucose_fasting', label: 'Fasting glucose', unit: 'mg/dL', better: 'down' }
]

/* Map readings onto the 300x100 viewBox the stylesheet expects. */
function buildPath(readings) {
  if (readings.length < 2) return null
  const values = readings.map((r) => r.value)
  const min = Math.min(...values)
  const max = Math.max(...values)
  const span = max - min || 1

  const points = readings.map((r, i) => {
    const x = (i / (readings.length - 1)) * 300
    const y = 88 - ((r.value - min) / span) * 68 // 20..88, inverted for SVG
    return [Number(x.toFixed(1)), Number(y.toFixed(1))]
  })

  const line = points.map(([x, y], i) => `${i === 0 ? 'M' : 'L'}${x} ${y}`).join(' ')
  const area = `${line} L300 100 L0 100 Z`
  return { line, area, last: points[points.length - 1] }
}

function Chart({ config, readings }) {
  const path = buildPath(readings)
  const latest = readings[readings.length - 1]
  const first = readings[0]
  const delta = latest && first ? latest.value - first.value : 0
  const improving = config.better === 'down' ? delta < 0 : delta > 0
  const gradientId = `grad-${config.kind}`

  return (
    <div className="graph">
      <div className="g-head">
        <b>{config.label}</b>
        <span className="val">
          {latest ? `${latest.value} ${config.unit}` : '—'}
          {readings.length > 1 && (
            <small>{improving ? '▼' : '▲'} {Math.abs(delta).toFixed(1)}</small>
          )}
        </span>
      </div>
      <svg className="chart" viewBox="0 0 300 100" preserveAspectRatio="xMidYMid meet">
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#b3122a" stopOpacity=".16" />
            <stop offset="1" stopColor="#b3122a" stopOpacity="0" />
          </linearGradient>
        </defs>
        <line className="g-grid" x1="0" y1="25" x2="300" y2="25" />
        <line className="g-grid" x1="0" y1="55" x2="300" y2="55" />
        <line className="g-grid" x1="0" y1="85" x2="300" y2="85" />
        {path ? (
          <>
            <path fill={`url(#${gradientId})`} d={path.area} />
            <path className="g-line draw" d={path.line} />
            <circle className="g-pt" cx={path.last[0]} cy={path.last[1]} r="3.4" />
          </>
        ) : (
          <text x="150" y="58" textAnchor="middle" fontSize="11" fill="#98a2b3">
            Not enough readings yet
          </text>
        )}
      </svg>
    </div>
  )
}

export default function Snapshot() {
  const { patient } = useAuth()
  const patientId = patient?.id

  const { data, loading, error, reload } = useResource(
    async () => {
      const series = await Promise.all(
        CHARTS.map((c) => api.vitals(patientId, { kind: c.kind, days: 730 }))
      )
      const [timeline, prescriptions, reports] = await Promise.all([
        api.timeline(patientId, { limit: 200 }),
        api.prescriptions(patientId),
        api.reports(patientId)
      ])
      return { series, timeline, prescriptions, reports }
    },
    [patientId],
    { enabled: Boolean(patientId) }
  )

  const body = () => {
    if (loading) return <Loading label="Loading your measurements…" rows={4} />
    if (error) return <ErrorState error={error} onRetry={reload} />

    const consultations = data.timeline.filter((e) => e.kind === 'consultation').length
    const year = new Date().getFullYear()
    const thisYear = (iso) => new Date(iso).getFullYear() === year

    return (
      <div className="snap reveal">
        <div>
          <div className="eyebrow">Health snapshot</div>
          <div className="snap-title">Your health, at a glance.</div>
          <p className="muted" style={{ maxWidth: 340, marginTop: 14 }}>
            Measurements recorded in your profile, drawn straight from your visits and lab reports.
          </p>
          <div className="insight">
            <b>HealthNexus insight</b>
            <p>
              {consultations} consultation{consultations === 1 ? '' : 's'} ·{' '}
              {data.prescriptions.length} prescription version{data.prescriptions.length === 1 ? '' : 's'} ·{' '}
              {data.reports.filter((r) => thisYear(r.issued_at)).length} lab investigation
              {data.reports.filter((r) => thisYear(r.issued_at)).length === 1 ? '' : 's'} on record.
            </p>
          </div>
        </div>
        <div className="graphs">
          {CHARTS.map((config, i) => (
            <Chart key={config.kind} config={config} readings={data.series[i] || []} />
          ))}
        </div>
      </div>
    )
  }

  return (
    <section id="snapshot" data-chapter="Your Records" data-nav="Snapshot">
      {body()}
    </section>
  )
}
