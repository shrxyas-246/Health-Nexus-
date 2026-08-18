import { useEffect, useRef, useState } from 'react'
import { useUI } from '../context/UIContext.jsx'
import { useResource } from '../hooks/useResource.js'
import { api } from '../lib/api.js'
import { time } from '../lib/format.js'
import { Loading, ErrorState } from '../components/States.jsx'

const KIND_ICON = {
  medicine: '💊',
  water: '💧',
  exercise: '🏃',
  sleep: '🌙',
  diet: '🥗',
  appointment: '📅',
  vitals: '📈'
}

function Reminders() {
  const { toast } = useUI()
  const { data, loading, error, reload } = useResource(() => api.remindersToday(), [])
  const [saving, setSaving] = useState(null)

  const complete = async (tick) => {
    setSaving(tick.reminder_id + tick.due_at)
    try {
      await api.completeReminder(tick.reminder_id, { due_at: tick.due_at })
      reload()
    } catch (err) {
      toast(err.detail || 'Could not update that')
    } finally {
      setSaving(null)
    }
  }

  if (loading) return <Loading label="Loading today's plan…" rows={4} />
  if (error) return <ErrorState error={error} onRetry={reload} />

  const done = data.filter((t) => t.completed).length

  return (
    <div className="reminders card">
      <div className="head">
        <h3 style={{ fontSize: 14 }}>Today&apos;s reminders</h3>
        <span className="muted" style={{ fontSize: 12 }}>{done} of {data.length} done</span>
      </div>
      <div className="rem-list">
        {data.map((tick) => {
          const key = tick.reminder_id + tick.due_at
          return (
            <div className={`rem${tick.completed ? ' done' : ''}`} key={key}>
              <span className="rem-ico" aria-hidden="true">{KIND_ICON[tick.kind] || '•'}</span>
              <div className="rem-body">
                <b>{tick.title}</b>
                <span>{time(tick.due_at)}{tick.description ? ` · ${tick.description}` : ''}</span>
              </div>
              <button
                className={`rem-check${tick.completed ? ' on' : ''}`}
                disabled={tick.completed || saving === key}
                onClick={() => complete(tick)}
                aria-label={tick.completed ? 'Completed' : `Mark ${tick.title} done`}
              >
                {tick.completed ? '✓' : ''}
              </button>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function Chatbot() {
  const [history, setHistory] = useState([])
  const [question, setQuestion] = useState('')
  const [busy, setBusy] = useState(false)
  const endRef = useRef(null)

  useEffect(() => {
    api.chatbotHistory().then(setHistory).catch(() => setHistory([]))
  }, [])

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }, [history])

  const ask = async (e) => {
    e.preventDefault()
    const text = question.trim()
    if (!text || busy) return
    setBusy(true)
    setQuestion('')
    try {
      const pair = await api.askChatbot(text)
      setHistory((prev) => [...prev, ...pair])
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="bot card">
      <div className="head">
        <h3 style={{ fontSize: 14 }}>Health assistant</h3>
        <span className="live"><i className="pulse"></i>General guidance</span>
      </div>

      <div className="bot-log">
        {history.length === 0 && (
          <p className="muted" style={{ fontSize: 13 }}>
            Ask a general question about sleep, diet, hydration or your medicines.
            For anything about your specific condition, message your doctor.
          </p>
        )}
        {history.map((m) => (
          <div className={`bubble ${m.role}${m.escalated_to_doctor ? ' urgent' : ''}`} key={m.id}>
            {m.body}
          </div>
        ))}
        <div ref={endRef} />
      </div>

      <form className="bot-form" onSubmit={ask}>
        <input
          value={question}
          placeholder="How much water should I drink?"
          onChange={(e) => setQuestion(e.target.value)}
          disabled={busy}
        />
        <button className="btn red" type="submit" disabled={busy || !question.trim()}>
          {busy ? '…' : 'Ask'}
        </button>
      </form>
    </div>
  )
}

export default function Today() {
  return (
    <section id="today" data-chapter="Your Records" data-nav="Today">
      <div className="section-head reveal">
        <div>
          <div className="eyebrow">Your day</div>
          <h2>Stay on track.</h2>
          <p className="muted">
            Medicine, water, movement and sleep reminders drawn from your prescription and care plan.
          </p>
        </div>
      </div>
      <div className="today-grid reveal">
        <Reminders />
        <Chatbot />
      </div>
    </section>
  )
}
