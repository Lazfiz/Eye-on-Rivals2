import { NextResponse } from 'next/server';
import path from 'path';
import fs from 'fs/promises';
import { spawn } from 'child_process';
import crypto from 'crypto';

export const runtime = 'nodejs';

const DEFAULT_COMPANIES = ['TopCon', 'Zeiss', 'Canon', 'OptoVue', 'Nidek'];

function nowIso(): string {
  return new Date().toISOString();
}

async function readJsonSafe<T = any>(filePath: string): Promise<T | null> {
  try {
    const txt = await fs.readFile(filePath, 'utf8');
    return JSON.parse(txt) as T;
  } catch (err: any) {
    if (err && err.code === 'ENOENT') return null;
    throw err;
  }
}

async function writeJsonAtomic(filePath: string, data: unknown): Promise<void> {
  const tmp = filePath + '.tmp';
  await fs.writeFile(tmp, JSON.stringify(data));
  await fs.rename(tmp, filePath);
}

async function exists(filePath: string): Promise<boolean> {
  try {
    await fs.access(filePath);
    return true;
  } catch {
    return false;
  }
}

function buildInitialSnapshot(companies: string[], runId: string) {
  const perCompany: Record<string, any> = Object.fromEntries(
    companies.map((c) => [
      c,
      {
        state: 'queued',
        elapsedMs: 0,
        etaMs: null,
        subtasks: [
          { name: 'News', state: 'queued', elapsedMs: 0, etaMs: null, items: 0, errors: 0 },
          { name: 'Jobs', state: 'queued', elapsedMs: 0, etaMs: null, items: 0, errors: 0 },
          { name: 'Patents', state: 'queued', elapsedMs: 0, etaMs: null, items: 0, errors: 0 },
        ],
      },
    ])
  );
  const ts = nowIso();
  return {
    runId,
    startedAt: ts,
    updatedAt: ts,
    v: 1,
    elapsedMs: 0,
    etaMs: null,
    status: 'running',
    overall: { total: companies.length, done: 0, percent: 0 },
    current: { company: null, subtask: null, stepIndex: 0, stepCount: companies.length },
    perCompany,
    pid: null,
    logTail: [],
    summary: { totalItems: 0, totalErrors: 0, finishedAt: null, totalDurationMs: null },
  };
}

export async function POST(req: Request) {
  const projectRoot = process.cwd();
  const backendDir = path.join(projectRoot, 'backend');
  const progressPath = path.join(backendDir, 'progress.json');
  const cancelPath = path.join(backendDir, 'cancel.json');
  const timingsPath = path.join(backendDir, 'timings.json');

  let body: any = {};
  try {
    body = await req.json();
  } catch {}

  const companiesInput =
    Array.isArray(body?.companies) && body.companies.length
      ? body.companies.map((x: any) => String(x))
      : DEFAULT_COMPANIES;

  const runId = crypto.randomUUID();
  const snapshot = buildInitialSnapshot(companiesInput, runId);

  try {
    const existing = await readJsonSafe<any>(progressPath);
    if (existing && existing.status === 'running' && typeof existing.runId === 'string' && existing.runId) {
      return NextResponse.json(
        { error: 'run-already-active', runId: existing.runId },
        { status: 409 }
      );
    }

    await writeJsonAtomic(progressPath, snapshot);

    const scriptPath = path.join(backendDir, 'scraper_tool', 'ScraperRunner.py');
    const isWin = process.platform === 'win32';
    const venvPath = path.join(
      backendDir,
      '.venv',
      isWin ? path.join('Scripts', 'python.exe') : path.join('bin', 'python')
    );

    let cmd: string;
    let args: string[];
    if (await exists(venvPath)) {
      cmd = venvPath;
      args = [scriptPath];
    } else if (isWin) {
      cmd = 'py';
      args = ['-3', scriptPath];
    } else {
      cmd = 'python3';
      args = [scriptPath];
    }

    const child = spawn(cmd, args, {
      cwd: backendDir,
      env: { ...process.env, PYTHONPATH: backendDir, RUN_ID: runId },
      detached: true,
      stdio: 'ignore',
    });
    child.unref();

    return NextResponse.json({ runId, startedAt: snapshot.startedAt }, { status: 202 });
  } catch (err: any) {
    return NextResponse.json({ error: String(err?.message || err || 'spawn-failed') }, { status: 500 });
  }
}
