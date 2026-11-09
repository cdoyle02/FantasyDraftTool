/**
 * Browser-local Workbook DFS pool persistence (Dexie).
 *
 * Survives tab close; scoped to this browser profile. Migrates once from the
 * legacy sessionStorage keys used before Phase C.
 */

import { db } from '../data/db'

export type WorkbookPoolManualTag = 'target' | 'fade'

export const WORKBOOK_POOL_STORE_ID = 'active' as const

/** Legacy sessionStorage keys — read once then cleared after Dexie migrate. */
export const WORKBOOK_POOL_CSV_STORAGE_KEY = 'workbook-pool-csv-text'
const WORKBOOK_POOL_TAGS_STORAGE_KEY = 'workbook-pool-manual-tags'

export interface WorkbookPoolPersisted {
  id: typeof WORKBOOK_POOL_STORE_ID
  csvText: string
  manualTags: Record<string, WorkbookPoolManualTag>
  updatedAt: number
}

function readLegacySession(): {
  csvText: string
  manualTags: Record<string, WorkbookPoolManualTag>
} {
  let csvText = ''
  let manualTags: Record<string, WorkbookPoolManualTag> = {}
  try {
    csvText = sessionStorage.getItem(WORKBOOK_POOL_CSV_STORAGE_KEY) ?? ''
    const rawTags = sessionStorage.getItem(WORKBOOK_POOL_TAGS_STORAGE_KEY)
    if (rawTags) {
      manualTags = JSON.parse(rawTags) as Record<string, WorkbookPoolManualTag>
    }
  } catch {
    // private mode / unavailable
  }
  return { csvText, manualTags }
}

function clearLegacySession() {
  try {
    sessionStorage.removeItem(WORKBOOK_POOL_CSV_STORAGE_KEY)
    sessionStorage.removeItem(WORKBOOK_POOL_TAGS_STORAGE_KEY)
  } catch {
    // ignore
  }
}

/** Load pool CSV + tags from Dexie, migrating legacy sessionStorage when present. */
export async function loadWorkbookPool(): Promise<WorkbookPoolPersisted> {
  const existing = await db.workbookPool.get(WORKBOOK_POOL_STORE_ID)
  if (existing) {
    return existing
  }

  const legacy = readLegacySession()
  const row: WorkbookPoolPersisted = {
    id: WORKBOOK_POOL_STORE_ID,
    csvText: legacy.csvText,
    manualTags: legacy.manualTags,
    updatedAt: Date.now()
  }
  if (legacy.csvText || Object.keys(legacy.manualTags).length > 0) {
    await db.workbookPool.put(row)
    clearLegacySession()
  }
  return row
}

export async function saveWorkbookPoolCsv(csvText: string): Promise<void> {
  const current = await loadWorkbookPool()
  await db.workbookPool.put({
    ...current,
    csvText,
    updatedAt: Date.now()
  })
}

export async function saveWorkbookPoolTags(
  manualTags: Record<string, WorkbookPoolManualTag>
): Promise<void> {
  const current = await loadWorkbookPool()
  await db.workbookPool.put({
    ...current,
    manualTags,
    updatedAt: Date.now()
  })
}
