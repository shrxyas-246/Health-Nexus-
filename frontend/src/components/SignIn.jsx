import { useState } from 'react'
import { useAuth } from '../context/AuthContext.jsx'

const DEMO_ACCOUNTS = [
  { email: 'rahul.verma@example.com', label: 'Rahul Verma', note: 'Premium patient, full history' },
  { email: 'aisha.khan@example.com', label: 'Aisha Khan', note: 'Free tier patient' }
]

export default function SignIn() {
  const { login } = useAuth()
  const [email, setEmail] = useState('rahul.verma@example.com')
  const [password, setPassword] = useState('Password123!')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      await login(email, password)
    } catch (err) {
      setError(err.detail || 'Could not sign in')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="signin">
      <form className="signin-card card" onSubmit={submit}>
        <svg className="mark" viewBox="0 0 40 40" fill="none" aria-hidden="true" style={{ width: 44, height: 44 }}>
          <rect x="1" y="1" width="38" height="38" rx="10" fill="#b3122a" />
          <path d="M20 12v13M13.5 18.5h13" stroke="#fff" strokeWidth="3.4" strokeLinecap="round" />
        </svg>
        <div className="eyebrow" style={{ marginTop: 18 }}>HealthNexus</div>
        <h1 style={{ fontSize: 26, margin: '4px 0 6px' }}>Sign in to your record</h1>
        <p className="muted" style={{ fontSize: 14 }}>
          Your health record, prescriptions and care team — in one place.
        </p>

        <label className="field">
          <span>Email</span>
          <input type="email" value={email} required autoComplete="username"
                 onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label className="field">
          <span>Password</span>
          <input type="password" value={password} required autoComplete="current-password"
                 onChange={(e) => setPassword(e.target.value)} />
        </label>

        {error && <div className="form-error">{error}</div>}

        <button className="btn red" type="submit" disabled={busy}
                style={{ width: '100%', justifyContent: 'center', marginTop: 4 }}>
          {busy ? 'Signing in…' : 'Sign in'}
        </button>

        <div className="demo-accounts">
          <small>Demo accounts — password <code>Password123!</code></small>
          {DEMO_ACCOUNTS.map((a) => (
            <button key={a.email} type="button" className="demo-row"
                    onClick={() => { setEmail(a.email); setPassword('Password123!') }}>
              <b>{a.label}</b><span>{a.note}</span>
            </button>
          ))}
        </div>
      </form>
    </div>
  )
}
