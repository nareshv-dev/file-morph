import { useState } from 'react'
import { api, navigate } from '../api.js'

export default function AccountPage({ user, onUserChange }) {
  const [name, setName] = useState(user.display_name)
  const [passwords, setPasswords] = useState({ current_password: '', new_password: '' })
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  async function profile(event) { event.preventDefault(); setError(''); try { const data = await api('/api/users/me', { method: 'PATCH', body: JSON.stringify({ display_name: name }) }); onUserChange(data.user); setMessage('Profile updated.') } catch (requestError) { setError(requestError.message) } }
  async function password(event) { event.preventDefault(); setError(''); try { await api('/api/users/me/password', { method: 'PATCH', body: JSON.stringify(passwords) }); onUserChange(null); navigate('/login') } catch (requestError) { setError(requestError.message) } }
  async function remove() { if (!window.confirm('Permanently delete your account, history, uploaded files, and converted files?')) return; await api('/api/users/me', { method: 'DELETE' }); onUserChange(null); navigate('/') }
  return <main className="account-layout" id="main"><section className="page-heading"><div className="eyebrow"><span /> ACCOUNT SETTINGS</div><h1>Your account.</h1><p>{user.email}</p></section>{(message || error) && <p className={error ? 'form-error' : 'form-success'} role="status">{error || message}</p>}<div className="settings-grid"><form className="settings-section" onSubmit={profile}><h2>Profile</h2><label>Display name<input value={name} onChange={(event) => setName(event.target.value)} /></label><button className="primary-button">Save profile</button></form><form className="settings-section" onSubmit={password}><h2>Change password</h2><label>Current password<input type="password" autoComplete="current-password" value={passwords.current_password} onChange={(event) => setPasswords({ ...passwords, current_password: event.target.value })} /></label><label>New password<input type="password" minLength="8" autoComplete="new-password" value={passwords.new_password} onChange={(event) => setPasswords({ ...passwords, new_password: event.target.value })} /></label><button className="secondary-button">Change password</button></form></div><section className="danger-zone"><h2>Delete account</h2><p>This permanently removes your account, history, uploaded files, and converted files.</p><button className="danger-button" onClick={remove}>Delete my account</button></section></main>
}
