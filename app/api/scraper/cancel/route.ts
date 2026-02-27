import { NextResponse } from 'next/server';
import path from 'path';
import fs from 'fs/promises';

export const runtime = 'nodejs';

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

export async function POST(req: Request) {
  try {
    let body: any = {};
    try {
      body = await req.json();
    } catch {
      body = {};
    }
    const runId = typeof body?.runId === 'string' ? body.runId : null;
    if (!runId) {
      return NextResponse.json(
        { error: 'missing-runId' },
        { status: 400, headers: { 'Cache-Control': 'no-store', 'Content-Type': 'application/json' } }
      );
    }

    const projectRoot = process.cwd();
    const backendDir = path.join(projectRoot, 'backend');
    const progressPath = path.join(backendDir, 'progress.json');
    const cancelPath = path.join(backendDir, 'cancel.json');

    // Attempt to read progress.json but treat transient read/parse issues as non-fatal.
    // If present and runId mismatches, return 404 as before.
    let validated = false;
    try {
      const txt = await fs.readFile(progressPath, 'utf8');
      const snapshot: any = JSON.parse(txt);
      if (snapshot && snapshot.runId !== runId) {
        return NextResponse.json(
          { error: 'run-mismatch' },
          { status: 404, headers: { 'Cache-Control': 'no-store', 'Content-Type': 'application/json' } }
        );
      }
      validated = !!snapshot && snapshot.runId === runId;
    } catch (err: any) {
      // Missing (ENOENT), transient permission (EPERM), or parse (SyntaxError) -> proceed without 500
      const isSyntax = err && (err.name === 'SyntaxError' || err.code === 'SYNTAX_ERROR');
      if (!(err && (err.code === 'ENOENT' || err.code === 'EPERM' || isSyntax))) {
        // Unexpected I/O error -> escalate
        throw err;
      }
      validated = false;
    }

    await writeJsonAtomic(cancelPath, { runId, ts: nowIso() });

    return NextResponse.json(
      { ok: true, validated },
      { status: 202, headers: { 'Cache-Control': 'no-store', 'Content-Type': 'application/json' } }
    );
  } catch (err: any) {
    return NextResponse.json(
      { error: String(err?.message || err || 'cancel-failed') },
      { status: 500, headers: { 'Cache-Control': 'no-store', 'Content-Type': 'application/json' } }
    );
  }
}