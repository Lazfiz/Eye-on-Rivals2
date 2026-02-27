import { NextResponse } from 'next/server';
import path from 'path';
import fs from 'fs/promises';

export const runtime = 'nodejs';
const STALE_HEARTBEAT_MS = Number(process.env.SCRAPER_STALE_HEARTBEAT_MS || 120000);

export function nowIso(): string {
  return new Date().toISOString();
}

export async function readJsonSafe<T = any>(filePath: string): Promise<T | null> {
  try {
    const txt = await fs.readFile(filePath, 'utf8');
    return JSON.parse(txt) as T;
  } catch (err: any) {
    if (err && err.code === 'ENOENT') return null;
    throw err;
  }
}

export async function writeJsonAtomic(filePath: string, data: unknown): Promise<void> {
  const tmp = filePath + '.tmp';
  await fs.writeFile(tmp, JSON.stringify(data));
  await fs.rename(tmp, filePath);
}

export async function GET(req: Request) {
  try {
    const url = new URL(req.url);
    const runId = url.searchParams.get('runId');
    if (!runId) {
      return NextResponse.json({ error: 'missing-runId' }, { status: 400, headers: { 'Cache-Control': 'no-store', 'Content-Type': 'application/json' } });
    }

    const projectRoot = process.cwd();
    const backendDir = path.join(projectRoot, 'backend');
    const progressPath = path.join(backendDir, 'progress.json');

    const snapshot = await readJsonSafe<any>(progressPath);
    const headers = { 'Cache-Control': 'no-store', 'Content-Type': 'application/json' } as Record<string, string>;

    if (!snapshot) {
      return NextResponse.json({ error: 'no-progress' }, { status: 404, headers });
    }
    if (snapshot.runId !== runId) {
      return NextResponse.json({ error: 'run-mismatch' }, { status: 404, headers });
    }

    const pidState = (pid: unknown): 'alive' | 'dead' | 'unknown' => {
      if (typeof pid !== 'number' || !Number.isFinite(pid) || pid <= 0) return 'dead';
      try {
        process.kill(pid, 0);
        return 'alive';
      } catch (err: any) {
        const code = String(err?.code || '').toUpperCase();
        const msg = String(err?.message || '').toLowerCase();
        if (code === 'ESRCH' || msg.includes('no such process') || msg.includes('not found')) return 'dead';
        if (code === 'EPERM' || code === 'EACCES' || msg.includes('access is denied') || msg.includes('operation not permitted')) return 'unknown';
        return 'unknown';
      }
    };

    const staleReason = (() => {
      if (snapshot.status !== 'running') return null;
      const hb = Date.parse(String(snapshot.updatedAt || ''));
      const now = Date.now();
      const heartbeatStale = !Number.isFinite(hb) || now - hb > STALE_HEARTBEAT_MS;
      const pid = pidState(snapshot.pid);
      if (pid === 'dead') return 'pid_not_alive';
      if (pid === 'unknown' && heartbeatStale) return 'pid_unknown_heartbeat_stale';
      if (heartbeatStale) return 'heartbeat_stale';
      return null;
    })();

    if (staleReason) {
      const logTail = Array.isArray(snapshot.logTail) ? snapshot.logTail.slice(-99) : [];
      logTail.push({
        ts: nowIso(),
        type: 'error',
        company: null,
        subtask: null,
        message: `stale_worker:${staleReason}`,
      });
      const nextSnapshot = {
        ...snapshot,
        status: 'error',
        updatedAt: nowIso(),
        current: { ...(snapshot.current || {}), company: null, subtask: null },
        logTail,
        summary: {
          ...(snapshot.summary || {}),
          finishedAt: snapshot?.summary?.finishedAt || nowIso(),
          totalDurationMs: snapshot?.summary?.totalDurationMs ?? snapshot?.elapsedMs ?? 0,
        },
      };
      await writeJsonAtomic(progressPath, nextSnapshot);
      return NextResponse.json(nextSnapshot, { status: 200, headers });
    }

    return NextResponse.json(snapshot, { status: 200, headers });
  } catch (err: any) {
    return NextResponse.json({ error: String(err?.message || err || 'progress-failed') }, { status: 500, headers: { 'Cache-Control': 'no-store', 'Content-Type': 'application/json' } });
  }
}
