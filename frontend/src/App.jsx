import { useEffect, useMemo, useState } from 'react'
import TopNav from './components/TopNav.jsx'
import ChapterBar from './components/ChapterBar.jsx'
import Footer from './components/Footer.jsx'
import Modal from './components/Modal.jsx'
import Toast from './components/Toast.jsx'
import Profile from './sections/Profile.jsx'
import Snapshot from './sections/Snapshot.jsx'
import Prescriptions from './sections/Prescriptions.jsx'
import History from './sections/History.jsx'
import Billing from './sections/Billing.jsx'
import Insurance from './sections/Insurance.jsx'
import Doctors from './sections/Doctors.jsx'
import Pharmacy from './sections/Pharmacy.jsx'
import Insights from './sections/Insights.jsx'
import Plus from './sections/Plus.jsx'

/* Section metadata — keeps chapter bar in sync with the DOM */
const SECTIONS = [
  { id: 'profile',       chapter: 'Your Records',        nav: 'Profile' },
  { id: 'snapshot',      chapter: 'Your Records',        nav: 'Snapshot' },
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
  const [activeId, setActiveId] = useState('profile')

  const activeSection = useMemo(
    () => SECTIONS.find((s) => s.id === activeId) || SECTIONS[0],
    [activeId]
  )

  const chapterLinks = useMemo(
    () => SECTIONS.filter((s) => s.chapter === activeSection.chapter).map((s) => ({ id: s.id, label: s.nav })),
    [activeSection]
  )

  /* Scroll spy */
  useEffect(() => {
    const els = SECTIONS.map((s) => document.getElementById(s.id)).filter(Boolean)
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => { if (e.isIntersecting) setActiveId(e.target.id) })
      },
      { rootMargin: '-40% 0px -55% 0px', threshold: 0 }
    )
    els.forEach((el) => io.observe(el))
    return () => io.disconnect()
  }, [])

  /* Reveal-on-scroll */
  useEffect(() => {
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
    document.querySelectorAll('.reveal').forEach((el) => io.observe(el))
    return () => io.disconnect()
  }, [])

  /* Charts, bars, progress bars — animate when their section enters */
  useEffect(() => {
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (!e.isIntersecting) return
          e.target.querySelectorAll('.g-line.draw').forEach((l) => l.classList.add('on'))
          e.target.querySelectorAll('.g-bar').forEach((b) => {
            const h = +b.dataset.h
            b.setAttribute('height', h)
            b.setAttribute('y', 85 - h)
          })
          e.target.querySelectorAll('.progress .bar i').forEach((i) => {
            i.style.width = i.dataset.w + '%'
          })
          io.unobserve(e.target)
        })
      },
      { threshold: 0.25 }
    )
    ;['snapshot', 'insurance'].forEach((id) => {
      const el = document.getElementById(id)
      if (el) io.observe(el)
    })
    return () => io.disconnect()
  }, [])

  /* Timeline rail fill + event reveal */
  useEffect(() => {
    const tl = document.getElementById('timeline')
    const rail = document.getElementById('railFill')
    if (!tl || !rail) return
    const events = [...document.querySelectorAll('.event')]
    const fx = () => {
      const r = tl.getBoundingClientRect()
      const p = Math.max(0, Math.min(1, (window.innerHeight * 0.72 - r.top) / r.height))
      rail.style.height = p * 100 + '%'
      events.forEach((ev) => {
        if (ev.getBoundingClientRect().top < window.innerHeight * 0.8) ev.classList.add('show')
      })
    }
    fx()
    window.addEventListener('scroll', fx, { passive: true })
    window.addEventListener('resize', fx)
    return () => {
      window.removeEventListener('scroll', fx)
      window.removeEventListener('resize', fx)
    }
  }, [])

  return (
    <>
      <TopNav activeId={activeId} />
      <ChapterBar chapter={activeSection.chapter} links={chapterLinks} activeId={activeId} />
      <main>
        <Profile />
        <Snapshot />
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
