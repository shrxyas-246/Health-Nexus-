export default function Snapshot() {
  return (
    <section id="snapshot" data-chapter="Your Records" data-nav="Snapshot">
      <div className="snap reveal">
        <div>
          <div className="eyebrow">Health snapshot</div>
          <div className="snap-title">Your health, at a glance.</div>
          <p className="muted" style={{ maxWidth: 340, marginTop: 14 }}>
            A concise view of the measurements already recorded in your profile over the last 12 months.
          </p>
          <div className="insight">
            <b>HealthNexus insight</b>
            <p>5 consultations · 3 prescription updates · 4 lab investigations in the last year.</p>
          </div>
        </div>
        <div className="graphs">
          <div className="graph">
            <div className="g-head">
              <b>Weight trend</b>
              <span className="val">68.4 kg<small>▼ 2.1</small></span>
            </div>
            <svg className="chart" viewBox="0 0 300 100" preserveAspectRatio="xMidYMid meet">
              <defs>
                <linearGradient id="gw" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0" stopColor="#b3122a" stopOpacity=".16" />
                  <stop offset="1" stopColor="#b3122a" stopOpacity="0" />
                </linearGradient>
              </defs>
              <line className="g-grid" x1="0" y1="25" x2="300" y2="25" />
              <line className="g-grid" x1="0" y1="55" x2="300" y2="55" />
              <line className="g-grid" x1="0" y1="85" x2="300" y2="85" />
              <path fill="url(#gw)" d="M0 72 L33 64 L66 67 L99 52 L132 55 L165 41 L198 46 L231 34 L264 37 L300 26 L300 100 L0 100 Z" />
              <path className="g-line draw" d="M0 72 L33 64 L66 67 L99 52 L132 55 L165 41 L198 46 L231 34 L264 37 L300 26" />
              <circle className="g-pt" cx="300" cy="26" r="3.4" />
            </svg>
          </div>
          <div className="graph">
            <div className="g-head">
              <b>Blood glucose</b>
              <span className="val">102 mg/dL<small>Stable</small></span>
            </div>
            <svg className="chart" viewBox="0 0 300 100" preserveAspectRatio="xMidYMid meet">
              <defs>
                <linearGradient id="gg" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0" stopColor="#b3122a" stopOpacity=".16" />
                  <stop offset="1" stopColor="#b3122a" stopOpacity="0" />
                </linearGradient>
              </defs>
              <line className="g-grid" x1="0" y1="25" x2="300" y2="25" />
              <line className="g-grid" x1="0" y1="55" x2="300" y2="55" />
              <line className="g-grid" x1="0" y1="85" x2="300" y2="85" />
              <path fill="url(#gg)" d="M0 58 L37 62 L74 44 L111 54 L148 46 L185 56 L222 42 L259 50 L300 40 L300 100 L0 100 Z" />
              <path className="g-line draw" d="M0 58 L37 62 L74 44 L111 54 L148 46 L185 56 L222 42 L259 50 L300 40" />
              <circle className="g-pt" cx="300" cy="40" r="3.4" />
            </svg>
          </div>
          <div className="graph">
            <div className="g-head">
              <b>Blood pressure</b>
              <span className="val">118/76<small>Optimal</small></span>
            </div>
            <svg className="chart" viewBox="0 0 300 100" preserveAspectRatio="xMidYMid meet">
              <defs>
                <linearGradient id="gb" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0" stopColor="#b3122a" stopOpacity=".16" />
                  <stop offset="1" stopColor="#b3122a" stopOpacity="0" />
                </linearGradient>
              </defs>
              <line className="g-grid" x1="0" y1="25" x2="300" y2="25" />
              <line className="g-grid" x1="0" y1="55" x2="300" y2="55" />
              <line className="g-grid" x1="0" y1="85" x2="300" y2="85" />
              <path fill="url(#gb)" d="M0 56 L30 62 L60 38 L90 52 L120 42 L150 54 L180 36 L210 48 L240 40 L270 46 L300 32 L300 100 L0 100 Z" />
              <path className="g-line draw" d="M0 56 L30 62 L60 38 L90 52 L120 42 L150 54 L180 36 L210 48 L240 40 L270 46 L300 32" />
              <circle className="g-pt" cx="300" cy="32" r="3.4" />
            </svg>
          </div>
          <div className="graph">
            <div className="g-head">
              <b>Upcoming follow-ups</b>
              <span className="val">3<small>Next 90d</small></span>
            </div>
            <svg className="chart" viewBox="0 0 300 100" preserveAspectRatio="xMidYMid meet">
              <line className="g-grid" x1="0" y1="25" x2="300" y2="25" />
              <line className="g-grid" x1="0" y1="55" x2="300" y2="55" />
              <line className="g-grid" x1="0" y1="85" x2="300" y2="85" />
              <rect className="g-bar" x="18" y="85" width="34" height="0" rx="4" data-h="30" />
              <rect className="g-bar" x="75" y="85" width="34" height="0" rx="4" data-h="52" />
              <rect className="g-bar" x="132" y="85" width="34" height="0" rx="4" data-h="20" />
              <rect className="g-bar" x="189" y="85" width="34" height="0" rx="4" data-h="62" />
              <rect className="g-bar" x="246" y="85" width="34" height="0" rx="4" data-h="40" />
            </svg>
          </div>
        </div>
      </div>
    </section>
  )
}
