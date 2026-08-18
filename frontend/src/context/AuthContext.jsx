import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { api, getToken, setToken } from '../lib/api.js'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [patient, setPatient] = useState(null)
  const [status, setStatus] = useState('loading') // loading | anon | ready

  const loadSession = useCallback(async () => {
    if (!getToken()) {
      setStatus('anon')
      return
    }
    try {
      const [me, profile] = await Promise.all([api.me(), api.profile()])
      setUser(me)
      setPatient(profile)
      setStatus('ready')
    } catch {
      // Expired or invalid token — drop it and show the sign-in screen.
      setToken(null)
      setUser(null)
      setPatient(null)
      setStatus('anon')
    }
  }, [])

  useEffect(() => { loadSession() }, [loadSession])

  const login = useCallback(async (email, password) => {
    const { access_token } = await api.login(email, password)
    setToken(access_token)
    await loadSession()
  }, [loadSession])

  const logout = useCallback(() => {
    setToken(null)
    setUser(null)
    setPatient(null)
    setStatus('anon')
  }, [])

  const refreshPatient = useCallback(async () => {
    setPatient(await api.profile())
  }, [])

  return (
    <AuthContext.Provider value={{ user, patient, status, login, logout, refreshPatient }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
