import { useUI } from '../context/UIContext.jsx'

export default function Billing() {
  const { toast } = useUI()
  return (
    <section id="billing" data-chapter="Billing & Insurance" data-nav="Billing">
      <div className="section-head reveal">
        <div>
          <div className="eyebrow">Healthcare finances</div>
          <h2>Medical billing</h2>
          <p className="muted">Bills, payments and insurance-linked expenses in one place.</p>
        </div>
        <button className="btn red" onClick={() => toast('Billing export prepared')}>Export billing</button>
      </div>
      <div className="stat-grid reveal">
        <div className="stat card hoverable">
          <div className="s-ico">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 2v20M17 5H9a3 3 0 0 0 0 6h6a3 3 0 0 1 0 6H7" strokeLinecap="round" />
            </svg>
          </div>
          <h3>₹38,450</h3>
          <p>Total medical expenses this year</p>
        </div>
        <div className="stat card hoverable">
          <div className="s-ico">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="m5 12 4 4 10-10" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
          <h3>₹29,000</h3>
          <p>Insurance-covered amount</p>
        </div>
        <div className="stat card hoverable">
          <div className="s-ico">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="9" />
              <path d="M12 7v5l3 2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
          <h3>₹4,200</h3>
          <p>Pending reimbursement</p>
        </div>
        <div className="stat card hoverable">
          <div className="s-ico">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="4" y="4" width="16" height="16" rx="2" />
              <path d="M4 9h16M9 4v16" />
            </svg>
          </div>
          <h3>6</h3>
          <p>Digital bills stored</p>
        </div>
      </div>
    </section>
  )
}
