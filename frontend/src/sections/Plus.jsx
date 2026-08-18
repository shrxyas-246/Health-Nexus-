import { useState } from 'react'
import { useUI } from '../context/UIContext.jsx'
import { useAuth } from '../context/AuthContext.jsx'
import { useResource } from '../hooks/useResource.js'
import { api } from '../lib/api.js'
import { money } from '../lib/format.js'
import { Loading, ErrorState } from '../components/States.jsx'

const KIND_LABEL = { diet: 'Diet', workout: 'Movement', lifestyle: 'Lifestyle' }

/* The advice payload is model-generated, so render whatever shape came back. */
function AdviceDetail({ payload }) {
  if (!payload) return null

  if (payload.targets || payload.meals) {
    return (
      <>
        {payload.targets && (
          <div className="advice-targets">
            {Object.entries(payload.targets).map(([key, value]) => (
              <span key={key}><b>{value}</b>{key.replace(/_/g, ' ')}</span>
            ))}
          </div>
        )}
        {payload.meals && (
          <ul className="advice-list">
            {Object.entries(payload.meals).map(([meal, text]) => (
              <li key={meal}><b>{meal}</b> {text}</li>
            ))}
          </ul>
        )}
        {payload.avoid?.length > 0 && (
          <div className="warn-line">Avoid: {payload.avoid.join(' · ')}</div>
        )}
      </>
    )
  }

  if (payload.sessions) {
    return (
      <ul className="advice-list">
        {payload.sessions.map((s, i) => (
          <li key={i}>
            <b>{s.name}</b> {s.minutes} min{s.intensity ? ` · ${s.intensity}` : ''}
            {s.moves && <div className="muted" style={{ fontSize: 12 }}>{s.moves.join(' · ')}</div>}
          </li>
        ))}
      </ul>
    )
  }

  if (payload.change) {
    return <ul className="advice-list"><li><b>{payload.change}</b> {payload.expected_effect}</li></ul>
  }
  return null
}

export default function Plus() {
  const { toast } = useUI()
  const { patient, refreshPatient } = useAuth()
  const [busy, setBusy] = useState(false)

  const { data, loading, error, reload } = useResource(
    async () => {
      const subscription = await api.subscription()
      if (!patient?.is_premium) return { subscription, advice: [] }
      const advice = await api.dailyAdvice().catch(() => [])
      return { subscription, advice }
    },
    [patient?.is_premium],
    { enabled: Boolean(patient) }
  )

  const subscribe = async () => {
    setBusy(true)
    try {
      await api.subscribe({ tier: 'plus', billing_cycle: 'monthly' })
      await refreshPatient()
      reload()
      toast('HealthNexus Plus is active')
    } catch (err) {
      toast(err.detail || 'Could not start the subscription')
    } finally {
      setBusy(false)
    }
  }

  const cancel = async () => {
    if (!window.confirm('Cancel HealthNexus Plus? Your recommendations will switch off.')) return
    setBusy(true)
    try {
      await api.cancelSubscription()
      await refreshPatient()
      reload()
      toast('Subscription cancelled')
    } catch (err) {
      toast(err.detail || 'Could not cancel')
    } finally {
      setBusy(false)
    }
  }

  const isPremium = patient?.is_premium

  return (
    <section id="plus" data-chapter="Care & Insights" data-nav="Plus" style={{ borderBottom: 0 }}>
      <div className="plus reveal">
        <div>
          <div className="eyebrow">HealthNexus Plus</div>
          <h2>{isPremium ? 'Your daily health plan.' : 'Your health. One connected journey.'}</h2>
          <p>
            {isPremium
              ? 'Built from your records, your current prescription and your doctor’s advice — refreshed every day.'
              : 'Personalised diet, movement and lifestyle guidance, plus the best-matched doctors, labs, pharmacies and policies for your condition.'}
          </p>
        </div>
        <div className="price">
          <b>{money(data?.subscription?.price ?? 299)}</b>
          <span className="per"> / {data?.subscription?.billing_cycle === 'yearly' ? 'year' : 'month'}</span>
          <div>
            {isPremium ? (
              <button className="btn" style={{ marginTop: 12 }} onClick={cancel} disabled={busy}>
                {busy ? 'Working…' : 'Cancel subscription'}
              </button>
            ) : (
              <button className="btn red" style={{ marginTop: 12 }} onClick={subscribe} disabled={busy}>
                {busy ? 'Activating…' : 'Subscribe now'}
              </button>
            )}
          </div>
        </div>
      </div>

      {isPremium && (
        <div className="advice-grid reveal">
          {loading && <Loading label="Preparing today's plan…" rows={3} />}
          {error && <ErrorState error={error} onRetry={reload} />}
          {!loading && !error && data.advice.length === 0 && (
            <div className="state">
              <b>No plan generated yet</b>
              <small className="muted">Today’s recommendations will appear here once the model has run.</small>
            </div>
          )}
          {!loading && !error && data.advice.map((item) => (
            <div className="advice card" key={item.id}>
              <span className="tag">{KIND_LABEL[item.kind] || item.kind}</span>
              <h3>{item.title}</h3>
              {item.rationale && <p className="muted">{item.rationale}</p>}
              <AdviceDetail payload={item.payload} />
            </div>
          ))}
        </div>
      )}
    </section>
  )
}
