import { createContext, useCallback, useContext, useRef, useState } from 'react'

const UIContext = createContext(null)

export function UIProvider({ children }) {
  const [toastMsg, setToastMsg] = useState('')
  const [toastOn, setToastOn] = useState(false)
  const [modalState, setModalState] = useState({ open: false, title: '', body: '' })
  const timer = useRef(null)

  const toast = useCallback((msg) => {
    setToastMsg(msg)
    setToastOn(true)
    clearTimeout(timer.current)
    timer.current = setTimeout(() => setToastOn(false), 2200)
  }, [])

  const modal = useCallback((title, body) => {
    setModalState({ open: true, title, body })
  }, [])

  const closeModal = useCallback(() => {
    setModalState((s) => ({ ...s, open: false }))
  }, [])

  const download = useCallback(() => {
    const text = `HEALTHNEXUS — DEMO MEDICAL HISTORY
Patient: Rahul Verma
Medical ID: HNX-482913

18 Aug 2026 — Doctor consultation — Dr. Ananya Sharma — BP review, prescription updated
16 Aug 2026 — Blood test — HbA1c 5.8%, glucose 102 mg/dL
20 Aug 2025 — Hospital admission — General ward (discharged 23 Aug)

Prototype data only. Not medical advice.`
    const a = document.createElement('a')
    a.href = URL.createObjectURL(new Blob([text], { type: 'text/plain' }))
    a.download = 'HealthNexus-Medical-History.txt'
    a.click()
    toast('Medical history downloaded')
  }, [toast])

  return (
    <UIContext.Provider value={{ toast, modal, closeModal, download, toastMsg, toastOn, modalState }}>
      {children}
    </UIContext.Provider>
  )
}

export const useUI = () => useContext(UIContext)
