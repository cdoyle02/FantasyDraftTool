import { FormEvent, useState } from 'react'
import { setApiToken } from './client'

interface ApiTokenPromptProps {
  /** Called after the token is stored so the view can retry its request. */
  onSaved: () => void
  message?: string
}

/**
 * Minimal household API-token entry. Shown when the API returns 401 under
 * FANTASY_DRAFT_API_TOKEN. The token stays in localStorage only — never in the bundle.
 */
export function ApiTokenPrompt({
  onSaved,
  message = 'Enter the household API token to load Week boards.'
}: ApiTokenPromptProps) {
  const [value, setValue] = useState('')

  const onSubmit = (event: FormEvent) => {
    event.preventDefault()
    const trimmed = value.trim()
    if (!trimmed) return
    setApiToken(trimmed)
    onSaved()
  }

  return (
    <form
      role="alert"
      data-testid="api-token-prompt"
      onSubmit={onSubmit}
      className="rounded-lg border border-amber-300/30 bg-amber-300/5 px-4 py-3 text-sm text-amber-100"
    >
      <p className="mb-2">{message}</p>
      <div className="flex flex-wrap items-center gap-2">
        <input
          type="password"
          autoComplete="off"
          data-testid="api-token-input"
          className="min-w-[12rem] flex-1 rounded-lg border border-line bg-ink px-3 py-2 text-sm text-slate-100"
          placeholder="Household API token"
          value={value}
          onChange={(event) => setValue(event.target.value)}
        />
        <button className="button-secondary" type="submit" data-testid="api-token-save">
          Save & retry
        </button>
      </div>
    </form>
  )
}
