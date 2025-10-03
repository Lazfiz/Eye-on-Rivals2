import { NextResponse } from 'next/server'
import { promises as fs } from 'fs'
import path from 'path'

export const runtime = 'nodejs'

type SummaryValue = { text: string; model?: string | null } | null

type PostBody = {
  summaries: Record<string, SummaryValue>
}

const summariesPath = path.join(process.cwd(), 'backend', 'summaries.json')

export async function GET() {
  try {
    const content = await fs.readFile(summariesPath, 'utf-8')
    const data = JSON.parse(content)
    const summaries = data.summaries ?? {}
    return NextResponse.json({ summaries, updatedAt: data.updatedAt ?? null })
  } catch (err: any) {
    if (err && (err.code === 'ENOENT' || err.code === 'ENOTDIR')) {
      return NextResponse.json({ summaries: {}, updatedAt: null })
    }
    return NextResponse.json({ error: err?.message ?? 'Failed to read summaries' }, { status: 500 })
  }
}

export async function POST(req: Request) {
  try {
    const body = (await req.json().catch(() => ({}))) as Partial<PostBody>
    if (!body || typeof body !== 'object' || !body.summaries || typeof body.summaries !== 'object') {
      return NextResponse.json({ error: 'Invalid payload. Expect { summaries: Record<string, {text, model?}|null> }' }, { status: 400 })
    }
    const payload = {
      summaries: body.summaries,
      updatedAt: new Date().toISOString(),
    }
    await fs.writeFile(summariesPath, JSON.stringify(payload, null, 2), 'utf-8')
    return NextResponse.json(payload)
  } catch (error: any) {
    return NextResponse.json({ error: error?.message ?? 'Failed to write summaries' }, { status: 500 })
  }
}