'use client'

import { useCallback, useEffect, useRef, useState } from 'react'

// Types and helpers
export type SubtaskState = {
  name: string
  state: 'queued' | 'running' | 'done' | 'error' | 'canceled' | 'skipped'
  elapsedMs: number
  etaMs: number | null
  items: number
  errors: number
}

export type PerCompanyState = {
  state: 'queued' | 'running' | 'done' | 'error' | 'canceled'
  elapsedMs: number
  etaMs: number | null
  subtasks: SubtaskState[]
}

export type ProgressSnapshot = {
  runId: string
  startedAt: string
  updatedAt: string
  v: number
  elapsedMs: number
  etaMs: number | null
  status: 'running' | 'done' | 'error' | 'canceled'
  overall: { total: number; done: number; percent: number }
  current: { company: string | null; subtask: string | null; stepIndex: number; stepCount: number }
  perCompany: Record<string, PerCompanyState>
  pid: number | null
  logTail: Array<{ ts: string; type: string; company: string | null; subtask: string | null; message: string }>
  summary: { totalItems: number; totalErrors: number; finishedAt: string | null; totalDurationMs: number | null }
}

export function formatMs(ms: number | null): string {
  if (ms == null || !isFinite(ms) || ms < 0) return '—'
  const total = Math.floor(ms / 1000)
  const m = Math.floor(total / 60)
  const s = total % 60
  const mm = String(m).padStart(2, '0')
  const ss = String(s).padStart(2, '0')
  return `${mm}:${ss}`
}

export function formatPercent(n: number | null | undefined): string {
  const v = typeof n === 'number' && isFinite(n) ? Math.max(0, Math.min(100, n)) : 0
  return `${v.toFixed(0)}%`
}

export type CompanyRow = {
  name: string
  state: 'queued' | 'running' | 'done' | 'error' | 'canceled'
  elapsedMs: number
  etaMs: number | null
}

export function selectCompanies(snap: ProgressSnapshot | null): CompanyRow[] {
  if (!snap || !snap.perCompany) return []
  const pc = snap.perCompany as Record<string, PerCompanyState>
  return Object.entries(pc).map(([name, info]) => ({
    name,
    state: info?.state ?? 'queued',
    elapsedMs: typeof info?.elapsedMs === 'number' ? info.elapsedMs : 0,
    etaMs: info?.etaMs ?? null,
  }))
}

type ClientState = 'idle' | 'starting' | 'running' | 'canceling' | 'done_success' | 'done_error' | 'done_canceled'

type HookResult = {
  state: ClientState
  snapshot: ProgressSnapshot | null
  runId: string | null
  start: (companies?: string[]) => Promise<void>
  cancel: () => Promise<void>
}

const POLL_BASE_MS = 750
const MAX_BACKOFF_MS = 3000

export function useScraperClient(): HookResult {
  const [state, setState] = useState<ClientState>('idle')
  const [snapshot, setSnapshot] = useState<ProgressSnapshot | null>(null)
  const [runId, setRunId] = useState<string | null>(null)
  const runIdRef = useRef<string | null>(null)

  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const stoppedRef = useRef(false)
  const consecutiveFailRef = useRef(0)

  const clearTimer = () => {
    if (timerRef.current) {
      clearTimeout(timerRef.current)
      timerRef.current = null
    }
  }

  const scheduleNext = (delayMs: number) => {
    clearTimer()
    timerRef.current = setTimeout(() => {
      void pollOnce()
    }, delayMs)
  }

  const stopPolling = () => {
    stoppedRef.current = true
    clearTimer()
  }

  const safeFetch = async (url: string, init?: RequestInit) => {
    const headers = new Headers(init?.headers || {})
    // Ensure no-store
    if (!headers.has('Cache-Control')) headers.set('Cache-Control', 'no-store')
    if (!headers.has('Content-Type') && init?.body) headers.set('Content-Type', 'application/json')
    const resp = await fetch(url, {
      ...init,
      headers,
      // In Next.js client, this hints caching too
      cache: 'no-store',
    })
    return resp
  }

  const applySnapshot = (snap: ProgressSnapshot | null) => {
    // If connection is flapping, push a warning line into a synthetic view
    if (snap && consecutiveFailRef.current >= 3) {
      const clone: ProgressSnapshot = {
        ...snap,
        logTail: [
          ...snap.logTail,
          {
            ts: new Date().toISOString(),
            type: 'warn',
            company: null,
            subtask: null,
            message: 'Connection glitch; retrying...',
          },
        ].slice(-12),
      }
      setSnapshot(clone)
    } else {
      setSnapshot(snap)
    }
  }

  const pollOnce = useCallback(async () => {
    if (stoppedRef.current) return
    const rid = runIdRef.current
    if (!rid) {
      // runId not yet committed; keep polling soon to avoid race
      scheduleNext(POLL_BASE_MS)
      return
    }
    try {
      const resp = await safeFetch(`/api/scraper/progress?runId=${encodeURIComponent(rid)}`, {
        method: 'GET',
      })
      if (!resp.ok) {
        consecutiveFailRef.current += 1
        const delay = Math.min(MAX_BACKOFF_MS, POLL_BASE_MS * (1 + consecutiveFailRef.current))
        scheduleNext(delay)
        return
      }

      let raw: any = null
      try {
        raw = await resp.json()
      } catch {
        // 200 but JSON parse failed; keep previous snapshot and backoff
        consecutiveFailRef.current += 1
        const delay = Math.min(MAX_BACKOFF_MS, POLL_BASE_MS * (1 + consecutiveFailRef.current))
        scheduleNext(delay)
        return
      }

      // Minimal shape validation
      if (!raw || typeof raw !== 'object' || typeof raw.status !== 'string' || !raw.overall || typeof raw.overall.percent !== 'number') {
        consecutiveFailRef.current += 1
        const delay = Math.min(MAX_BACKOFF_MS, POLL_BASE_MS * (1 + consecutiveFailRef.current))
        scheduleNext(delay)
        return
      }

      // RunId mismatch should not happen; warn and keep polling original runId
      if (raw.runId && raw.runId !== rid) {
        console.warn('Progress runId mismatch; ignoring snapshot from server', { expected: rid, got: raw.runId })
        scheduleNext(POLL_BASE_MS)
        return
      }

      const data = raw as ProgressSnapshot
      consecutiveFailRef.current = 0
      // Always apply snapshot, even when percent is 0
      applySnapshot(data)

      // Terminal states
      if (data.status === 'done') {
        setState('done_success')
        stopPolling()
        return
      }
      if (data.status === 'error') {
        setState('done_error')
        stopPolling()
        return
      }
      if (data.status === 'canceled') {
        setState('done_canceled')
        stopPolling()
        return
      }

      // keep running
      setState((prev) => (prev === 'starting' ? 'running' : prev))
      scheduleNext(POLL_BASE_MS)
    } catch {
      consecutiveFailRef.current += 1
      const delay = Math.min(MAX_BACKOFF_MS, POLL_BASE_MS * (1 + consecutiveFailRef.current))
      scheduleNext(delay)
    }
  }, [])

  const beginPolling = () => {
    stoppedRef.current = false
    consecutiveFailRef.current = 0
    clearTimer()
    scheduleNext(0)
  }

  const start = useCallback(async (companies?: string[]) => {
    if (state === 'running' || state === 'starting' || state === 'canceling') return
    setState('starting')
    applySnapshot(null)
    setRunId(null)
    stoppedRef.current = false
    consecutiveFailRef.current = 0
    clearTimer()

    try {
      const resp = await safeFetch('/api/scraper/start', {
        method: 'POST',
        body: JSON.stringify({ companies: Array.isArray(companies) && companies.length ? companies : undefined }),
      })
      if (resp.status !== 202) {
        // treat as error
        setState('done_error')
        return
      }
      const json = await resp.json()
      const newRunId = String(json?.runId || '')
      setRunId(newRunId || null)
      setState('running')

      // Fetch initial snapshot before starting interval; proceed even if it fails
      try {
        const initResp = await safeFetch(`/api/scraper/progress?runId=${encodeURIComponent(newRunId)}`, { method: 'GET' })
        if (initResp.ok) {
          const raw = await initResp.json().catch(() => null)
          if (raw && typeof raw === 'object' && typeof raw.status === 'string' && raw.overall && typeof raw.overall.percent === 'number') {
            applySnapshot(raw as ProgressSnapshot)
          }
        }
      } catch {
        // ignore; begin polling anyway
      }

      beginPolling()
    } catch {
      setState('done_error')
    }
  }, [state])

  const cancel = useCallback(async () => {
    if (!runId) return
    if (state !== 'running' && state !== 'starting' && state !== 'canceling') return
    setState('canceling')
    try {
      await safeFetch('/api/scraper/cancel', {
        method: 'POST',
        body: JSON.stringify({ runId }),
      })
      // Keep polling until server marks as canceled
      if (stoppedRef.current) beginPolling()
    } catch {
      // keep polling; server might still honor cancel file
      if (stoppedRef.current) beginPolling()
    }
  }, [runId, state])

  useEffect(() => {
    runIdRef.current = runId
  }, [runId])

  useEffect(() => {
    return () => {
      stopPolling()
    }
  }, [])

  return { state, snapshot, runId, start, cancel }
}