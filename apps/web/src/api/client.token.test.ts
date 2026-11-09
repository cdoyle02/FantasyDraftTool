import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  API_TOKEN_STORAGE_KEY,
  ApiAuthError,
  DraftApiClient,
  getApiToken,
  setApiToken
} from './client'

describe('DraftApiClient API token', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
  })

  afterEach(() => {
    localStorage.clear()
  })

  it('reads and writes the household token via localStorage', () => {
    expect(getApiToken()).toBe('')
    setApiToken('  secret-token  ')
    expect(localStorage.getItem(API_TOKEN_STORAGE_KEY)).toBe('secret-token')
    expect(getApiToken()).toBe('secret-token')
    setApiToken('')
    expect(localStorage.getItem(API_TOKEN_STORAGE_KEY)).toBeNull()
  })

  it('attaches X-Api-Token when a token is stored', async () => {
    setApiToken('household-secret')
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: 'ok' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' }
      })
    )
    vi.stubGlobal('fetch', fetchMock)

    const client = new DraftApiClient('http://api.test')
    await client.weekOdds()

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    const headers = new Headers(init.headers)
    expect(headers.get('X-Api-Token')).toBe('household-secret')
  })

  it('omits X-Api-Token when no token is stored', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: 'ok' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' }
      })
    )
    vi.stubGlobal('fetch', fetchMock)

    const client = new DraftApiClient('http://api.test')
    await client.weekOdds()

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    const headers = new Headers(init.headers)
    expect(headers.get('X-Api-Token')).toBeNull()
  })

  it('throws ApiAuthError on 401 responses', async () => {
    const fetchMock = vi.fn().mockImplementation(
      async () =>
        new Response(
          JSON.stringify({ error: { code: 'unauthorized', message: 'Invalid or missing API token' } }),
          { status: 401, headers: { 'Content-Type': 'application/json' } }
        )
    )
    vi.stubGlobal('fetch', fetchMock)

    const client = new DraftApiClient('http://api.test')
    const err = await client.weekOdds().then(
      () => null,
      (caught: unknown) => caught
    )
    expect(err).toBeInstanceOf(ApiAuthError)
    expect(err).toMatchObject({ message: 'Invalid or missing API token', status: 401 })
  })
})
