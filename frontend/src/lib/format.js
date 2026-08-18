/* Shared display formatting, so dates and money read the same everywhere. */

export const money = (value) =>
  value == null ? '—' : `₹${Number(value).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`

export const shortDate = (iso) =>
  iso ? new Date(iso).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) : '—'

export const dayMonth = (iso) =>
  iso ? new Date(iso).toLocaleDateString('en-IN', { day: '2-digit', month: 'short' }).toUpperCase() : '—'

export const time = (iso) =>
  iso ? new Date(iso).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }) : ''

export const relative = (iso) => {
  if (!iso) return ''
  const seconds = Math.round((Date.now() - new Date(iso).getTime()) / 1000)
  if (seconds < 60) return 'just now'
  const minutes = Math.round(seconds / 60)
  if (minutes < 60) return `${minutes} min ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours} hr ago`
  const days = Math.round(hours / 24)
  if (days < 30) return `${days} day${days === 1 ? '' : 's'} ago`
  return shortDate(iso)
}

export const titleCase = (value) =>
  (value || '').replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())

/* Map an API tone (ok | warn | bad | neutral) to the stylesheet's classes. */
export const toneClass = (tone) => (tone === 'ok' ? 'ok' : tone === 'bad' ? 'bad' : tone === 'warn' ? 'warn' : '')
