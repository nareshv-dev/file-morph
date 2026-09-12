import { useState } from 'react'
import { EyeIcon } from './Icons.jsx'
import { api, navigate } from '../api.js'

export default function AuthPage({ mode, onAuthenticated }) {
  const signup = mode === 'signup'
  const [form, setForm] = useState({ display_name: '', email: '', password: '' })
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function submit(event) {
    event.preventDefault(); setError(''); setLoading(true)
    try {
      const payload = await api(`/api/auth/${mode}`, { method: 'POST', body: JSON.stringify(form) })
      onAuthenticated(payload.user); navigate('/convert')
    } catch (requestError) { setError(requestError.message) } finally { setLoading(false) }
  }

  return (
    <main id="main" tabIndex="-1" className="auth-layout">
      <section className="auth-panel" aria-labelledby="auth-title">
        <div className="eyebrow"><span /> PRIVATE CONVERSION WORKSPACE</div>
        <h1 id="auth-title">{signup ? 'Create your FileMorph account.' : 'Welcome back.'}</h1>
        <p>{signup ? 'Keep conversions organized, downloadable, and private to your account.' : 'Log in to convert documents and open your conversion history.'}</p>
        <form onSubmit={submit} className="auth-form">
          {signup && <label>Display name<input required autoComplete="name" value={form.display_name} onChange={(event) => setForm({ ...form, display_name: event.target.value })} /></label>}
          <label>Email address<input required type="email" autoComplete="email" value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} /></label>
          <div className="form-field"><label htmlFor="auth-password">Password</label><span className="password-field"><input id="auth-password" required minLength="8" type={showPassword ? 'text' : 'password'} autoComplete={signup ? 'new-password' : 'current-password'} value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} /><button type="button" aria-label={showPassword ? 'Hide password' : 'Show password'} onClick={() => setShowPassword(!showPassword)}><EyeIcon hidden={showPassword} /></button></span></div>
          {error && <p className="form-error" role="alert">{error}</p>}
          <button className="primary-button" type="submit" disabled={loading}>{loading ? 'Please wait...' : signup ? 'Create account' : 'Log in'}</button>
        </form>
        <p className="auth-switch">{signup ? 'Already have an account?' : 'New to FileMorph?'} <a href={signup ? '/login' : '/signup'} onClick={(event) => { event.preventDefault(); navigate(signup ? '/login' : '/signup') }}>{signup ? 'Log in' : 'Create an account'}</a></p>
      </section>
    </main>
  )
}
