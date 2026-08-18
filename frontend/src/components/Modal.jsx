import { useEffect } from 'react'
import { useUI } from '../context/UIContext.jsx'

export default function Modal() {
  const { modalState, closeModal } = useUI()

  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') closeModal() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [closeModal])

  return (
    <div
      className={`modal${modalState.open ? ' open' : ''}`}
      onClick={(e) => { if (e.target === e.currentTarget) closeModal() }}
    >
      <div className="box">
        <div className="box-head">
          <div>
            <div className="eyebrow">HealthNexus</div>
            <h2 style={{ fontSize: 20 }}>{modalState.title}</h2>
          </div>
          <button className="close" onClick={closeModal} aria-label="Close">✕</button>
        </div>
        <pre>{modalState.body}</pre>
        <button className="btn red" onClick={closeModal}>Close</button>
      </div>
    </div>
  )
}
