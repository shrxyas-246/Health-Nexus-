import { useUI } from '../context/UIContext.jsx'
import { useResource } from '../hooks/useResource.js'
import { api } from '../lib/api.js'
import { money, shortDate, titleCase } from '../lib/format.js'
import { Loading, ErrorState } from '../components/States.jsx'

const RupeeIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M12 2v20M17 5H9a3 3 0 0 0 0 6h6a3 3 0 0 1 0 6H7" strokeLinecap="round" />
  </svg>
)
const CheckIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="m5 12 4 4 10-10" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
)
const ClockIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
)
const GridIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <rect x="4" y="4" width="16" height="16" rx="2" /><path d="M4 9h16M9 4v16" />
  </svg>
)

export default function Billing() {
  const { toast, modal } = useUI()
  const { data, loading, error, reload } = useResource(
    async () => {
      const [summary, payments] = await Promise.all([api.billingSummary(), api.payments({ limit: 50 })])
      return { summary, payments }
    },
    []
  )

  const exportBilling = () => {
    const rows = [
      'Date,Purpose,Payee,Amount,Status,Reference',
      ...data.payments.map((p) =>
        [shortDate(p.created_at), p.purpose, p.payee_name || '—', p.amount, p.status, p.gateway_ref]
          .map((v) => `"${v ?? ''}"`).join(',')
      )
    ].join('\n')

    const a = document.createElement('a')
    a.href = URL.createObjectURL(new Blob([rows], { type: 'text/csv' }))
    a.download = 'HealthNexus-Billing.csv'
    a.click()
    URL.revokeObjectURL(a.href)
    toast('Billing exported as CSV')
  }

  const body = () => {
    if (loading) return <Loading label="Loading your billing…" rows={4} />
    if (error) return <ErrorState error={error} onRetry={reload} />

    const { summary, payments } = data
    const stats = [
      { icon: <RupeeIcon />, value: money(summary.spent_this_year), label: 'Total medical expenses this year' },
      { icon: <CheckIcon />, value: money(summary.reimbursed_amount), label: 'Reimbursed by insurance' },
      { icon: <ClockIcon />, value: money(summary.pending_amount), label: 'Pending payment' },
      { icon: <GridIcon />, value: String(payments.length), label: 'Digital bills stored' }
    ]

    return (
      <>
        <div className="stat-grid reveal">
          {stats.map((s) => (
            <div className="stat card hoverable" key={s.label}>
              <div className="s-ico">{s.icon}</div>
              <h3>{s.value}</h3>
              <p>{s.label}</p>
            </div>
          ))}
        </div>

        <div className="ledger card reveal">
          <div className="ledger-head">
            <b>Recent transactions</b>
            <span className="muted" style={{ fontSize: 12 }}>All payments routed through HealthNexus</span>
          </div>
          {payments.slice(0, 8).map((p) => (
            <button className="ledger-row" key={p.id} onClick={() => modal(
              'Payment detail',
              [
                `Reference: ${p.gateway_ref}`,
                `Date: ${shortDate(p.created_at)}`,
                `Purpose: ${titleCase(p.purpose)}`,
                `Paid to: ${p.payee_name || 'HealthNexus'}`,
                `Amount: ${money(p.amount)}`,
                `Method: ${(p.method || '—').toUpperCase()}`,
                `Status: ${titleCase(p.status)}`,
                '',
                `Platform fee (${(p.commission_rate * 100).toFixed(0)}%): ${money(p.commission_amount)}`,
                `Settled to provider: ${money(p.payout_amount)}`
              ].join('\n')
            )}>
              <div className="l-main">
                <b>{p.description || titleCase(p.purpose)}</b>
                <span className="muted">{shortDate(p.created_at)} · {p.payee_name || 'HealthNexus'}</span>
              </div>
              <div className="l-amt">
                <b>{money(p.amount)}</b>
                <span className={`badge${p.status === 'paid' ? ' g' : ''}`}>{titleCase(p.status)}</span>
              </div>
            </button>
          ))}
        </div>
      </>
    )
  }

  return (
    <section id="billing" data-chapter="Billing & Insurance" data-nav="Billing">
      <div className="section-head reveal">
        <div>
          <div className="eyebrow">Healthcare finances</div>
          <h2>Medical billing</h2>
          <p className="muted">Bills, payments and insurance-linked expenses in one place.</p>
        </div>
        <button className="btn red" onClick={exportBilling} disabled={loading || !!error}>Export billing</button>
      </div>
      {body()}
    </section>
  )
}
