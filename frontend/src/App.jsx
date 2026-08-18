import { useEffect, useMemo, useState } from 'react'
import TopNav from './components/TopNav.jsx'
import ChapterBar from './components/ChapterBar.jsx'
import Footer from './components/Footer.jsx'
import Modal from './components/Modal.jsx'
import Toast from './components/Toast.jsx'
import SignIn from './components/SignIn.jsx'
import Profile from './sections/Profile.jsx'
import Snapshot from './sections/Snapshot.jsx'
import Today from './sections/Today.jsx'
import Prescriptions from './sections/Prescriptions.jsx'
import History from './sections/History.jsx'
import Billing from './sections/Billing.jsx'
import Insurance from './sections/Insurance.jsx'
import Doctors from './sections/Doctors.jsx'
import Pharmacy from './sections/Pharmacy.jsx'
import Insights from './sections/Insights.jsx'
import Plus from './sections/Plus.jsx'
import { useAuth } from './context/AuthContext.jsx'

/* Section metadata — keeps chapter bar in sync with the DOM */
const SECTIONS = [
  { id: 'profile',       chapter: 'Your Records',        nav: 'Profile' },
  { id: 'snapshot',      chapter: 'Your Records',        nav: 'Snapshot' },
  { id: 'today',         chapter: 'Your Records',        nav: 'Today' },
  { id: 'prescriptions', chapter: 'Your Records',        nav: 'Prescriptions' },
  { id: 'history',       chapter: 'Your Records',        nav: 'Medical History' },
  { id: 'billing',       chapter: 'Billing & Insurance', nav: 'Billing' },
  { id: 'insurance',     chapter: 'Billing & Insurance', nav: 'Insurance' },
  { id: 'doctors',       chapter: 'Care & Insights',     nav: 'Doctors' },
  { id: 'pharmacy',      chapter: 'Care & Insights',     nav: 'Pharmacy' },
  { id: 'insights',      chapter: 'Care & Insights',     nav: 'Insights' },
  { id: 'plus',          chapter: 'Care & Insights',     nav: 'Plus' }
]

export default function App() {
  const { status } = useAuth()
  const [activeId, setActiveId] = useState('profile')

  const activeSection = useMemo(
    () => SECTIONS.find((s) => s.id === activeId) || SECTIONS[0],
    [activeId]
  )

  const chapterLinks = useMemo(
    () => SECTIONS.filter((s) => s.chapter === activeSection.chapter).map((s) => ({ id: s.id, label: s.nav })),
    [activeSection]
  )

  const signedIn = status === 'ready'

  /* Scroll spy */
  useEffect(() => {
    if (!signedIn) return
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => { if (e.isIntersecting) setActiveId(e.target.id) })
      },
      { rootMargin: '-40% 0px -55% 0px', threshold: 0 }
    )
    SECTIONS.forEach((s) => {
      const el = document.getElementById(s.id)
      if (el) io.observe(el)
    })
    return () => io.disconnect()
  }, [signedIn])

  /* Reveal-on-scroll. Re-runs as sections finish loading and mount new nodes. */
  useEffect(() => {
    if (!signedIn) return
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) {
            e.target.classList.add('in')
            io.unobserve(e.target)
          }
        })
      },
      { rootMargin: '0px 0px -8% 0px', threshold: 0.08 }
    )
    const observe = () => document.querySelectorAll('.reveal:not(.in)').forEach((el) => io.observe(el))
    observe()

    const mo = new MutationObserver(observe)
    mo.observe(document.body, { childList: true, subtree: true })
    return () => { io.disconnect(); mo.disconnect() }
  }, [signedIn])

  /* Charts, bars and progress bars animate when their section enters view. */
  useEffect(() => {
    if (!signedIn) return
    const animate = (el) => {
      el.querySelectorAll('.g-line.draw').forEach((l) => l.classList.add('on'))
      el.querySelectorAll('.g-bar').forEach((b) => {
        const h = +b.dataset.h
        b.setAttribute('height', h)
        b.setAttribute('y', 85 - h)
      })
      el.querySelectorAll('.progress .bar i').forEach((i) => { i.style.width = `${i.dataset.w}%` })
    }
    const io = new IntersectionObserver(
      (entries) => entries.forEach((e) => { if (e.isIntersecting) { animate(e.target); io.unobserve(e.target) } }),
      { threshold: 0.2 }
    )
    const observe = () => ['snapshot', 'insurance'].forEach((id) => {
      const el = document.getElementById(id)
      if (el) io.observe(el)
    })
    observe()

    const mo = new MutationObserver(observe)
    mo.observe(document.body, { childList: true, subtree: true })
    return () => { io.disconnect(); mo.disconnect() }
  }, [signedIn])

  /* Timeline rail fill + event reveal */
  useEffect(() => {
    if (!signedIn) return
    const fx = () => {
      const tl = document.getElementById('timeline')
      const rail = document.getElementById('railFill')
      if (!tl || !rail) return
      const r = tl.getBoundingClientRect()
      const p = Math.max(0, Math.min(1, (window.innerHeight * 0.72 - r.top) / r.height))
      rail.style.height = `${p * 100}%`
      document.querySelectorAll('.event').forEach((ev) => {
        if (ev.getBoundingClientRect().top < window.innerHeight * 0.85) ev.classList.add('show')
      })
    }
    fx()
    const id = setInterval(fx, 400) // catches events that mount after a fetch
    window.addEventListener('scroll', fx, { passive: true })
    window.addEventListener('resize', fx)
    return () => {
      clearInterval(id)
      window.removeEventListener('scroll', fx)
      window.removeEventListener('resize', fx)
    }
  }, [signedIn])

  if (status === 'loading') {
    return <div className="boot"><span className="skeleton" /><small className="muted">Loading HealthNexus…</small></div>
  }
  if (status === 'anon') return <SignIn />

  return (
    <>
      <TopNav activeId={activeId} />
      <ChapterBar chapter={activeSection.chapter} links={chapterLinks} activeId={activeId} />
      <main>
        <Profile />
        <Snapshot />
        <Today />
        <Prescriptions />
        <History />
        <Billing />
        <Insurance />
        <Doctors />
        <Pharmacy />
        <Insights />
        <Plus />
      </main>
      <Footer />
      <Modal />
      <Toast />
    </>
  )
}
