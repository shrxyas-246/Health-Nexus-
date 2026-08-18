import { useUI } from '../context/UIContext.jsx'

export default function Toast() {
  const { toastOn, toastMsg } = useUI()
  return (
    <div className={`toast${toastOn ? ' show' : ''}`}>
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
        <path d="m5 12 4 4 10-10" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      <span>{toastMsg}</span>
    </div>
  )
}
