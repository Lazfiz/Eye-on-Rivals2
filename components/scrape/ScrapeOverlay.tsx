'use client'

import React, { useEffect, useMemo, useRef, useState } from 'react'
import { Progress } from '@/components/ui/progress'
import { Button } from '@/components/ui/button'
import type { ProgressSnapshot } from '@/components/scrape/useScraperClient'
import { formatMs, formatPercent } from '@/components/scrape/useScraperClient'

type Props = {
  open: boolean
  onCancelRequested: () => void
  snapshot: ProgressSnapshot | null
  compact?: boolean
  canceling?: boolean
}

function stateIcon(state: string): string {
  // queued = ○, running = ●, done = ✓, error = ⚠, canceled = ■
  switch (state) {
    case 'queued':
      return '○'
    case 'running':
      return '●'
    case 'done':
      return '✓'
    case 'error':
      return '⚠'
    case 'canceled':
      return '■'
    default:
      return '○'
  }
}

export default function ScrapeOverlay({ open, onCancelRequested, snapshot, compact, canceling }: Props) {
  const [isCompact, setIsCompact] = useState<boolean>(!!compact)
  const cancelRef = useRef<HTMLButtonElement | null>(null)

  useEffect(() => {
    setIsCompact(!!compact)
  }, [compact])

  useEffect(() => {
    if (open) {
      // Focus first actionable control for a11y
      setTimeout(() => cancelRef.current?.focus(), 0)
    }
  }, [open])

  const overallPercent = Math.max(0, Math.min(100, snapshot?.overall?.percent ?? 0))
  const currentCompany = snapshot?.current?.company || '—'
  const currentSubtask = snapshot?.current?.subtask || null
  const elapsedTxt = formatMs(snapshot?.elapsedMs ?? null)
  const etaTxt = snapshot?.etaMs != null ? formatMs(snapshot?.etaMs) : '—'

  const perCompanyEntries = useMemo(() => {
    const pc = snapshot?.perCompany || {}
    const entries = Object.entries(pc) as Array<[string, { state: string; elapsedMs?: number | null }]>
    // Stable sort by state progression: running first, then queued, then done/error/canceled by name
    const rank: Record<string, number> = { running: 0, queued: 1, done: 2, error: 2, canceled: 2 }
    return entries.sort((a, b) => {
      const ra = rank[a[1]?.state] ?? 9
      const rb = rank[b[1]?.state] ?? 9
      if (ra !== rb) return ra - rb
      return a[0].localeCompare(b[0])
    })
  }, [snapshot?.perCompany])

  const logTail = useMemo(() => {
    const tail = (snapshot?.logTail ?? []) as ProgressSnapshot['logTail']
    return tail.slice(Math.max(0, tail.length - 5))
  }, [snapshot?.logTail])

  if (!open) return null

  return (
    <div
      role="dialog"
      aria-modal="false"
      aria-label="Scraping in progress"
      className="fixed z-[60] bottom-2 right-2 md:bottom-4 md:right-4 pointer-events-auto mx-2 w-[90vw] max-w-md rounded-xl bg-white/90 shadow-2xl ring-1 ring-black/5 backdrop-blur-md"
    >
      {/* Header */}
      <div className="px-5 pt-5 pb-3 border-b border-black/5 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-blue-700">Scraping in progress</h2>
        <div className="text-sm font-medium text-blue-700">{formatPercent(overallPercent)}</div>
      </div>

      {/* Progress */}
      <div className="px-5 pt-4">
        <Progress value={overallPercent} className="h-2 bg-blue-100" />
      </div>

      {/* Inline status */}
      <div className="px-5 pt-3 text-sm text-blue-900/90" aria-live="polite">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <span className="font-medium">Current:</span>
          <span className="truncate max-w-[55%]" title={currentCompany || undefined}>{currentCompany}</span>
          {currentSubtask ? (
            <><span className="text-blue-500">•</span><span className="truncate" title={currentSubtask}>{currentSubtask}</span></>
          ) : null}
          <span className="text-blue-500">•</span>
          <span>Elapsed {elapsedTxt}</span>
          <span className="text-blue-500">•</span>
          <span>ETA {etaTxt}</span>
        </div>
      </div>

      {/* Details (per-company list) */}
      {!isCompact && (
        <div id="details" className="px-5 pt-4 pb-2 max-h-64 overflow-auto">
          <ul className="space-y-2">
            {perCompanyEntries.map(([name, info]) => {
              const ico = stateIcon(info?.state)
              const showTime = info?.state === 'running' || info?.state === 'done' || info?.state === 'error' || info?.state === 'canceled'
              const elapsed = formatMs(info?.elapsedMs ?? null)
              return (
                <li key={name} className="flex items-center justify-between text-sm">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="select-none">{ico}</span>
                    <span className="truncate" title={name}>{name}</span>
                  </div>
                  <div className="text-xs tabular-nums text-blue-900/70">
                    {showTime ? elapsed : '—'}
                  </div>
                </li>
              )
            })}
            {perCompanyEntries.length === 0 && (
              <li className="text-sm text-blue-900/70">
                {(snapshot?.overall?.total ?? 0) > 0
                  ? `Queued (${(snapshot?.overall?.total ?? snapshot?.current?.stepCount ?? 0)} companies)`
                  : 'No companies queued.'}
              </li>
            )}
          </ul>
        </div>
      )}

      {/* Optional log tail */}
      {logTail.length > 0 && (
        <div className="px-5 pt-2 pb-1">
          <div className="text-xs text-blue-900/60 mb-1">Recent activity</div>
          <ul className="space-y-1 text-xs text-blue-900/80 max-h-24 overflow-auto">
            {logTail.map((entry: ProgressSnapshot['logTail'][number], idx: number) => (
              <li key={idx} className="flex gap-2">
                <span className="text-blue-500/70 select-none">•</span>
                <span className="truncate">{entry.message}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Actions */}
      <div className="px-5 py-4 border-t border-black/5 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Button
            ref={cancelRef}
            onClick={onCancelRequested}
            className="bg-red-500 hover:bg-red-600 text-white"
            disabled={!!canceling || (snapshot?.status && snapshot.status !== 'running')}
            aria-disabled={!!canceling || (snapshot?.status && snapshot.status !== 'running') ? true : undefined}
            title={canceling ? 'Cancel requested…' : 'Cancel current scraping run'}
          >
            {canceling ? 'Canceling…' : 'Cancel scraping'}
          </Button>
        </div>
        <div>
          <Button
            variant="outline"
            className="border-blue-300 text-blue-700 hover:bg-blue-50"
            onClick={() => setIsCompact((v) => !v)}
            aria-expanded={!isCompact}
            aria-controls="details"
          >
            {isCompact ? 'Show details' : 'Hide details'}
          </Button>
        </div>
      </div>
    </div>
  )
}