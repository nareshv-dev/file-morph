import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import AuthPage from '../components/AuthPage.jsx'
import FileUpload from '../components/FileUpload.jsx'
import Workspace from '../components/Workspace.jsx'
import HistoryPage from '../components/HistoryPage.jsx'
import App from '../App.jsx'
import { api } from '../api.js'

vi.mock('../api.js', async (importOriginal) => ({ ...await importOriginal(), api: vi.fn() }))

beforeEach(() => { vi.clearAllMocks(); window.history.replaceState(null, '', '/') })

describe('authentication', () => {
  it('validates and submits signup', async () => {
    api.mockResolvedValue({ user: { id: 'one', email: 'one@example.com', display_name: 'One' } })
    const onAuthenticated = vi.fn(); const user = userEvent.setup()
    render(<AuthPage mode="signup" onAuthenticated={onAuthenticated} />)
    await user.type(screen.getByLabelText('Display name'), 'One')
    await user.type(screen.getByLabelText('Email address'), 'one@example.com')
    await user.type(screen.getByLabelText('Password'), 'StrongPass123')
    await user.click(screen.getByRole('button', { name: 'Create account' }))
    expect(onAuthenticated).toHaveBeenCalledWith(expect.objectContaining({ id: 'one' }))
  })

  it('shows login errors and toggles password visibility', async () => {
    api.mockRejectedValue(new Error('Email or password is incorrect.'))
    const user = userEvent.setup(); render(<AuthPage mode="login" onAuthenticated={vi.fn()} />)
    await user.type(screen.getByLabelText('Email address'), 'one@example.com')
    await user.type(screen.getByLabelText('Password'), 'WrongPass123')
    await user.click(screen.getByRole('button', { name: 'Show password' }))
    expect(screen.getByLabelText('Password')).toHaveAttribute('type', 'text')
    await user.click(screen.getByRole('button', { name: 'Log in' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Email or password is incorrect.')
  })

  it('redirects anonymous users away from history', async () => {
    window.history.replaceState(null, '', '/history'); api.mockRejectedValue(new Error('Authentication required.'))
    render(<App />)
    expect(await screen.findByRole('heading', { name: 'Welcome back.' })).toBeInTheDocument()
    expect(window.location.pathname).toBe('/login')
  })

  it('logs out and returns to public navigation', async () => {
    api.mockImplementation((path) => path === '/api/auth/me' ? Promise.resolve({ user: { id: 'one', display_name: 'One' } }) : Promise.resolve(null))
    const user = userEvent.setup(); render(<App />)
    await user.click(await screen.findByRole('button', { name: 'Log out' }))
    expect(await screen.findByRole('link', { name: 'Log in' })).toBeInTheDocument()
  })
})

describe('conversion workspace', () => {
  it('rejects an invalid upload', async () => {
    const setError = vi.fn(); const user = userEvent.setup({ applyAccept: false }); const { container } = render(<FileUpload file={null} onFile={vi.fn()} disabled={false} error="" setError={setError} acceptedExtensions={['pdf']} sourceLabel="PDF" />)
    await user.upload(container.querySelector('input[type=file]'), new File(['not pdf'], 'notes.txt', { type: 'text/plain' }))
    expect(setError).toHaveBeenCalled()
  })

  it('selects a new format and completes a conversion', async () => {
    api.mockResolvedValue({ job: { id: 'job', status: 'completed', output_filename: 'sample.docx', output_size: 100, expires_at: '2030-01-01T00:00:00Z' } })
    const user = userEvent.setup(); const { container } = render(<Workspace />)
    await user.selectOptions(screen.getByLabelText('Conversion format'), 'text-to-docx')
    await user.upload(container.querySelector('input[type=file]'), new File(['Readable text'], 'sample.txt', { type: 'text/plain' }))
    await user.click(screen.getByRole('button', { name: 'Convert to DOCX' }))
    expect(await screen.findByText('Conversion complete')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Download' })).toBeInTheDocument()
  })

  it('shows real conversion failures', async () => {
    api.mockResolvedValue({ job: { id: 'job', status: 'failed', failure_reason: 'Unsupported document feature.', expires_at: '2030-01-01T00:00:00Z' } })
    const user = userEvent.setup(); const { container } = render(<Workspace />)
    await user.upload(container.querySelector('input[type=file]'), new File(['%PDF-'], 'sample.pdf', { type: 'application/pdf' }))
    await user.click(screen.getByRole('button', { name: 'Convert to DOCX' }))
    expect(await screen.findByText('Conversion failed')).toBeInTheDocument()
    expect(screen.getByText('Unsupported document feature.')).toBeInTheDocument()
  })

  it('shows loading feedback while a request is pending', async () => {
    api.mockImplementation(() => new Promise(() => {}))
    const user = userEvent.setup(); const { container } = render(<Workspace />)
    await user.upload(container.querySelector('input[type=file]'), new File(['%PDF-'], 'sample.pdf', { type: 'application/pdf' }))
    await user.click(screen.getByRole('button', { name: 'Convert to DOCX' }))
    expect(screen.getByRole('status')).toHaveTextContent('Converting your document...')
  })
})

describe('history', () => {
  const job = { id: 'one', source_filename: 'sample.pdf', source_format: 'pdf', target_format: 'docx', source_size: 100, output_size: 200, status: 'completed', created_at: '2026-01-01T00:00:00Z', expires_at: '2030-01-01T00:00:00Z', output_filename: 'sample.docx' }
  it('renders and filters account history', async () => {
    api.mockResolvedValue({ items: [job], total: 1 })
    const user = userEvent.setup(); render(<HistoryPage />)
    expect(await screen.findByText('sample.pdf')).toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('Source'), 'pdf')
    await waitFor(() => expect(api).toHaveBeenLastCalledWith(expect.stringContaining('source_format=pdf')))
  })
  it('confirms before deleting a conversion', async () => {
    api.mockResolvedValue({ items: [job], total: 1 }); vi.spyOn(window, 'confirm').mockReturnValue(false)
    const user = userEvent.setup(); render(<HistoryPage />)
    await user.click(await screen.findByRole('button', { name: 'Delete sample.pdf' }))
    expect(window.confirm).toHaveBeenCalled()
    expect(api).not.toHaveBeenCalledWith('/api/conversions/one', { method: 'DELETE' })
    window.confirm.mockRestore()
  })

  it('requests the next history page', async () => {
    api.mockResolvedValue({ items: [job], total: 11 })
    const user = userEvent.setup(); render(<HistoryPage />)
    await screen.findByText('sample.pdf')
    await user.click(screen.getByRole('button', { name: 'Next' }))
    await waitFor(() => expect(api).toHaveBeenLastCalledWith(expect.stringContaining('page=2')))
  })
})
