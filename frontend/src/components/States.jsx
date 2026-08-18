/* Shared loading / empty / error placeholders, so every section degrades the same way. */

export function Loading({ label = 'Loading…', rows = 3 }) {
  return (
    <div className="state" role="status" aria-live="polite">
      <div className="skeleton-stack">
        {Array.from({ length: rows }, (_, i) => <span className="skeleton" key={i} />)}
      </div>
      <small className="muted">{label}</small>
    </div>
  )
}

export function Empty({ title = 'Nothing here yet', detail }) {
  return (
    <div className="state">
      <b>{title}</b>
      {detail && <small className="muted">{detail}</small>}
    </div>
  )
}

export function ErrorState({ error, onRetry }) {
  // 402 is the premium gate — it is a prompt to upgrade, not a failure.
  const isGate = error?.status === 402
  return (
    <div className={`state${isGate ? ' gate' : ' error'}`}>
      <b>{isGate ? 'Premium feature' : 'Could not load this'}</b>
      <small className="muted">{error?.detail || error?.message}</small>
      {!isGate && onRetry && (
        <button className="btn" style={{ marginTop: 10 }} onClick={onRetry}>Try again</button>
      )}
    </div>
  )
}

/** Render whichever of loading / error / empty / content applies. */
export function Resource({ loading, error, data, onRetry, empty, children, label }) {
  if (loading) return <Loading label={label} />
  if (error) return <ErrorState error={error} onRetry={onRetry} />
  if (!data || (Array.isArray(data) && data.length === 0)) return <Empty {...(empty || {})} />
  return children(data)
}
