import { useState } from 'react'
import { useUI } from '../context/UIContext.jsx'
import { useResource } from '../hooks/useResource.js'
import { api } from '../lib/api.js'
import { money, shortDate, titleCase } from '../lib/format.js'
import { Loading, ErrorState, Empty } from '../components/States.jsx'

const Check = () => (
  <span className="check">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
      <path d="m5 12 4 4 10-10" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  </span>
)

const SETTLED = new Set(['approved', 'partially_approved', 'settled'])

export default function Insurance() {
  const { toast, modal } = useUI()
  const [filing, setFiling] = useState(false)

  const { data, loading, error, reload } = useResource(
    async () => {
      const [policies, claims] = await Promise.all([api.policies(), api.claims()])
      return { policies, claims }
    },
    []
  )

  const startClaim = async () => {
    const policy = data.policies[0]
    if (!policy) return toast('Link a policy before filing a claim')

    const input = window.prompt('Claim amount (₹)', '4200')
    if (!input) return
    const amount = Number(input)
    if (!Number.isFinite(amount) || amount <= 0) return toast('Enter a valid amount')

    setFiling(true)
    try {
      const claim = await api.fileClaim({
        patient_policy_id: policy.id,
        amount_claimed: amount,
        treatment_type: 'reimbursement',
        description: 'Filed from the HealthNexus app'
      })
      toast(`Claim ${claim.claim_number} submitted`)
      reload()
    } catch (err) {
      toast(err.detail || 'Could not file the claim')
    } finally {
      setFiling(false)
    }
  }

  const body = () => {
    if (loading) return <Loading label="Loading your cover…" rows={4} />
    if (error) return <ErrorState error={error} onRetry={reload} />
    if (data.policies.length === 0) {
      return <Empty title="No policy linked" detail="Link your health policy to file claims from the app." />
    }

    const policy = data.policies[0]
    const claims = data.claims
    const latest = claims[0]

    return (
      <div className="insurance reveal">
        <div className="ins-card card">
          <div className="ins-head">
            <div>
              <b>{policy.insurer_name}</b>
              <span>{policy.plan_name} · {policy.policy_number}</span>
            </div>
            <span className={`badge${policy.is_active ? ' g' : ''}`}>{policy.is_active ? 'Active' : 'Lapsed'}</span>
          </div>

          <div className="claim"><Check /><div><b>Cover</b><span>{money(policy.cover_amount)} total</span></div></div>
          <div className="claim"><Check /><div><b>Used this year</b><span>{money(policy.used_amount)} claimed and settled</span></div></div>
          <div className="claim"><Check /><div><b>Remaining</b><span>{money(policy.remaining_amount)} available</span></div></div>
          <div className="claim"><Check /><div><b>Valid until</b><span>{shortDate(policy.ends_on)}</span></div></div>

          <div className="progress">
            <div className="bar"><i data-w={String(Math.min(policy.used_percent, 100))}></i></div>
            <div className="lbl"><span>Cover used</span><span>{policy.used_percent}%</span></div>
          </div>
        </div>

        <div className="ins-card card">
          <div className="eyebrow">Claims</div>
          <h3 style={{ fontSize: 18 }}>
            {claims.length ? `${claims.length} claim${claims.length === 1 ? '' : 's'} on record` : 'No claims yet'}
          </h3>

          {claims.slice(0, 4).map((c) => (
            <button
              key={c.id}
              className="claim-row"
              onClick={() => modal(
                `Claim ${c.claim_number}`,
                [
                  `Status: ${titleCase(c.status)}`,
                  `Type: ${titleCase(c.treatment_type || '—')}`,
                  `Claimed: ${money(c.amount_claimed)}`,
                  `Approved: ${money(c.amount_approved)}`,
                  c.hospital_name ? `Hospital: ${c.hospital_name}` : '',
                  c.submitted_at ? `Submitted: ${shortDate(c.submitted_at)}` : '',
                  c.settled_at ? `Settled: ${shortDate(c.settled_at)}` : '',
                  '',
                  c.reviewer_note || c.rejection_reason || c.description || ''
                ].filter(Boolean).join('\n')
              )}
            >
              <div>
                <b>{c.claim_number}</b>
                <span className="muted">{money(c.amount_claimed)} · {shortDate(c.submitted_at || c.created_at)}</span>
              </div>
              <span className={`badge${SETTLED.has(c.status) ? ' g' : ''}`}>{titleCase(c.status)}</span>
            </button>
          ))}

          {latest && (
            <div className="insight" style={{ maxWidth: 'none', marginTop: 14 }}>
              <b>Latest: {titleCase(latest.status)}</b>
              <p>{latest.reviewer_note || latest.rejection_reason || 'Awaiting insurer review.'}</p>
            </div>
          )}
        </div>
      </div>
    )
  }

  return (
    <section id="insurance" data-chapter="Billing & Insurance" data-nav="Insurance">
      <div className="section-head reveal">
        <div>
          <div className="eyebrow">Smart claims</div>
          <h2>Insurance without the paperwork.</h2>
          <p className="muted">
            Your verified records pre-fill eligible claim details. Final approval always stays with the insurer.
          </p>
        </div>
        <button className="btn red" onClick={startClaim} disabled={filing || loading || !!error}>
          {filing ? 'Filing…' : 'Start a claim'}
        </button>
      </div>
      {body()}
    </section>
  )
}
