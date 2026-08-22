import { afterEach, describe, expect, it, vi } from 'vitest'
import { createOfflineWorker } from './adapter'

describe('offline Python worker', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('uses a module worker required by the local Pyodide ESM runtime', () => {
    const worker = {} as Worker
    const WorkerMock = vi.fn(() => worker)
    vi.stubGlobal('Worker', WorkerMock)

    expect(createOfflineWorker()).toBe(worker)
    expect(WorkerMock).toHaveBeenCalledTimes(1)
    expect(WorkerMock.mock.calls[0][1]).toEqual({ type: 'module' })
    expect(WorkerMock.mock.calls[0][0]).toBeInstanceOf(URL)
  })
})
