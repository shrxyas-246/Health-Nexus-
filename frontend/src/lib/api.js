/* Thin fetch wrapper around the Health Nexus API.
   Vite proxies /api to the FastAPI server (see vite.config.js). */

const BASE = '/api/v1'
const TOKEN_KEY = 'hnx.token'

export const getToken = () => localStorage.getItem(TOKEN_KEY)
export const setToken = (t) => (t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY))

export class ApiError extends Error {
  constructor(status, detail) {
    super(detail || `Request failed (${status})`)
    this.status = status
    this.detail = detail
  }
}

async function request(path, { method = 'GET', body, auth = true } = {}) {
  const headers = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'

  const token = auth ? getToken() : null
  if (token) headers.Authorization = `Bearer ${token}`

  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body)
  })

  if (res.status === 204) return null

  const text = await res.text()
  const payload = text ? JSON.parse(text) : null

  if (!res.ok) {
    // FastAPI puts the human-readable reason in `detail`.
    const detail = typeof payload?.detail === 'string' ? payload.detail : `Request failed (${res.status})`
    throw new ApiError(res.status, detail)
  }
  return payload
}

const qs = (params = {}) => {
  const entries = Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== '')
  return entries.length ? `?${new URLSearchParams(entries)}` : ''
}

export const api = {
  /* auth */
  login: (email, password) => request('/auth/login', { method: 'POST', body: { email, password }, auth: false }),
  registerPatient: (payload) => request('/auth/register/patient', { method: 'POST', body: payload, auth: false }),
  me: () => request('/auth/me'),

  /* patient record */
  profile: () => request('/patients/me'),
  updateProfile: (payload) => request('/patients/me', { method: 'PATCH', body: payload }),
  summary: () => request('/patients/me/summary'),
  timeline: (patientId, params) => request(`/patients/${patientId}/timeline${qs(params)}`),
  addTimelineEvent: (patientId, payload) => request(`/patients/${patientId}/timeline`, { method: 'POST', body: payload }),
  conditions: (patientId) => request(`/patients/${patientId}/conditions`),
  surgeries: (patientId) => request(`/patients/${patientId}/surgeries`),
  vitals: (patientId, params) => request(`/patients/${patientId}/vitals${qs(params)}`),
  reports: (patientId) => request(`/patients/${patientId}/reports`),
  documents: (patientId) => request(`/patients/${patientId}/documents`),

  /* prescriptions */
  prescriptions: (patientId) => request(`/prescriptions/patients/${patientId}`),
  currentPrescription: (patientId) => request(`/prescriptions/patients/${patientId}/current`),
  prescriptionVersions: (id) => request(`/prescriptions/${id}/versions`),

  /* care */
  doctors: (params) => request(`/doctors${qs(params)}`),
  doctorRatings: (id) => request(`/doctors/${id}/ratings`),
  appointments: (params) => request(`/appointments/me${qs(params)}`),
  bookAppointment: (payload) => request('/appointments', { method: 'POST', body: payload }),

  /* labs */
  labs: (params) => request(`/labs${qs(params)}`),
  labTests: (labId) => request(`/labs/${labId}/tests`),
  bookLabOrder: (payload) => request('/labs/orders', { method: 'POST', body: payload }),
  labOrders: () => request('/labs/orders/me'),

  /* pharmacy */
  pharmacies: (params) => request(`/pharmacies${qs(params)}`),
  medicineOrders: () => request('/pharmacies/orders/me'),
  placeMedicineOrder: (payload) => request('/pharmacies/orders', { method: 'POST', body: payload }),

  /* money */
  billingSummary: () => request('/billing/summary'),
  payments: (params) => request(`/billing/payments/me${qs(params)}`),
  subscription: () => request('/billing/subscription/me'),
  subscribe: (payload) => request('/billing/subscription', { method: 'POST', body: payload }),
  cancelSubscription: () => request('/billing/subscription', { method: 'DELETE' }),

  /* insurance */
  policies: () => request('/insurance/policies/me'),
  claims: (params) => request(`/insurance/claims/me${qs(params)}`),
  fileClaim: (payload) => request('/insurance/claims', { method: 'POST', body: payload }),
  insurancePlans: (params) => request(`/insurance/plans${qs(params)}`),

  /* community */
  posts: (params) => request(`/posts${qs(params)}`),
  likePost: (id) => request(`/posts/${id}/like`, { method: 'POST' }),
  reviews: (targetKind, targetId) => request(`/reviews${qs({ target_kind: targetKind, target_id: targetId })}`),
  writeReview: (payload) => request('/reviews', { method: 'POST', body: payload }),
  threads: () => request('/chat/threads'),
  messages: (threadId) => request(`/chat/threads/${threadId}/messages`),
  sendMessage: (threadId, body) => request(`/chat/threads/${threadId}/messages`, { method: 'POST', body: { body } }),
  notifications: (params) => request(`/notifications/me${qs(params)}`),
  markNotificationsRead: () => request('/notifications/read-all', { method: 'POST' }),

  /* wellness */
  remindersToday: () => request('/wellness/reminders/today'),
  completeReminder: (id, payload) => request(`/wellness/reminders/${id}/complete`, { method: 'POST', body: payload }),
  reminders: () => request('/wellness/reminders'),
  askChatbot: (question) => request('/wellness/chatbot/ask', { method: 'POST', body: { question } }),
  chatbotHistory: () => request('/wellness/chatbot/history'),

  /* premium — ranked and written by the ML service (see ml/) */
  recommendedDoctors: (params) => request(`/recommendations/doctors${qs(params)}`),
  recommendedLabs: (params) => request(`/recommendations/labs${qs(params)}`),
  recommendedPharmacies: (params) => request(`/recommendations/pharmacies${qs(params)}`),
  recommendedHospitals: (params) => request(`/recommendations/hospitals${qs(params)}`),
  recommendedInsurance: (params) => request(`/recommendations/insurance${qs(params)}`),
  dailyAdvice: () => request('/recommendations/daily'),
  refreshAdvice: () => request('/recommendations/daily/refresh', { method: 'POST' }),
  dismissAdvice: (id) => request(`/recommendations/${id}/dismiss`, { method: 'POST' }),
  mlStatus: () => request('/ml/status'),

  /* emergency */
  triggerEmergency: (payload) => request('/emergency', { method: 'POST', body: payload }),
  activeEmergency: () => request('/emergency/active')
}
