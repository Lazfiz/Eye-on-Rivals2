import { NextResponse } from "next/server"
import { promises as fs } from "fs"
import path from "path"
import { GoogleGenerativeAI } from "@google/generative-ai"

export const runtime = "nodejs"

type DistItem = { name: string; value: number }
type DistPayload = { distribution: DistItem[]; updatedAt: string }

const STORAGE = path.join(process.cwd(), "backend", "market-share.json")

const COMPANIES = [
  "Zeiss",
  "Canon",
  "Optovue",
  "Heidelberg",
  "Topcon",
  "Optos",
  "Nidek",
  "Others",
]

function normalizeName(raw: string): string {
  const s = raw.trim().toLowerCase()
  if (!s) return "Others"
  if (/(carl\s+)?zeiss/.test(s) || /meditec/.test(s)) return "Zeiss"
  if (/canon/.test(s)) return "Canon"
  if (/opto\s*vue|optovue/.test(s)) return "Optovue"
  if (/heidelberg/.test(s)) return "Heidelberg"
  if (/topcon/.test(s)) return "Topcon"
  if (/optos/.test(s)) return "Optos"
  if (/nidek/.test(s)) return "Nidek"
  if (/other|rest|misc|remaining/.test(s)) return "Others"
  return raw.trim()
}

function clamp2(n: number): number {
  if (!isFinite(n)) return 0
  const x = Math.max(0, n)
  return Math.round(x * 100) / 100
}

function renormalizeTo100(items: DistItem[]): DistItem[] {
  const sum = items.reduce((a, b) => a + (b.value || 0), 0)
  if (sum === 0) return items
  const scale = 100 / sum
  const scaled = items.map((i) => ({ ...i, value: clamp2(i.value * scale) }))
  // Fix rounding drift on "Others"
  const drift = 100 - scaled.reduce((a, b) => a + b.value, 0)
  const idx = scaled.findIndex((i) => i.name === "Others")
  if (idx >= 0) {
    scaled[idx].value = clamp2(scaled[idx].value + drift)
  } else if (scaled.length > 0) {
    scaled[scaled.length - 1].value = clamp2(scaled[scaled.length - 1].value + drift)
  }
  return scaled
}

function coalesceToCompanies(map: Record<string, number>): DistItem[] {
  // Start with zeros for all expected companies
  const out: Record<string, number> = Object.fromEntries(COMPANIES.map((c) => [c, 0]))
  // Merge parsed values
  for (const [k, v] of Object.entries(map)) {
    const key = normalizeName(k)
    if (!out[key] && !COMPANIES.includes(key)) {
      // unknown bucket - add to Others
      out["Others"] += Number(v) || 0
    } else {
      out[key] += Number(v) || 0
    }
  }
  // Ensure total = 100 (adjust Others)
  let sum = Object.values(out).reduce((a, b) => a + b, 0)
  if (sum > 100.0001 || sum < 99.9999) {
    const diff = clamp2(100 - sum)
    out["Others"] = clamp2(out["Others"] + diff)
    sum = Object.values(out).reduce((a, b) => a + b, 0)
  }
  const items = Object.entries(out).map(([name, value]) => ({ name, value: clamp2(value) }))
  return renormalizeTo100(items)
}

function parseListTextToMap(text: string): Record<string, number> {
  const lines = text
    .replace(/```json[\s\S]*?```/gi, (m) => m) // keep code fences for a sec
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter(Boolean)

  const map: Record<string, number> = {}
  const pairRe = /^[-*\u2022]?\s*([^:]+?)\s*[:\-]\s*([0-9]+(?:\.[0-9]+)?)\s*%?\s*$/
  for (const line of lines) {
    const m = line.match(pairRe)
    if (!m) continue
    const name = m[1].trim()
    const num = parseFloat(m[2])
    if (!isNaN(num)) {
      map[name] = (map[name] || 0) + num
    }
  }
  return map
}

async function readPersisted(): Promise<DistPayload | null> {
  try {
    const raw = await fs.readFile(STORAGE, "utf-8")
    const json = JSON.parse(raw)
    if (Array.isArray(json?.distribution)) {
      return json as DistPayload
    }
    return null
  } catch {
    return null
  }
}

async function writePersisted(payload: DistPayload) {
  await fs.mkdir(path.dirname(STORAGE), { recursive: true })
  await fs.writeFile(STORAGE, JSON.stringify(payload, null, 2), "utf-8")
}

export async function GET() {
  try {
    const existing = await readPersisted()
    if (existing) {
      return NextResponse.json(existing)
    }
    // No persisted - return empty to let frontend fallback
    return NextResponse.json({ distribution: [], updatedAt: null })
  } catch (err: any) {
    return NextResponse.json({ error: err?.message || "Failed to read market share" }, { status: 500 })
  }
}

export async function POST() {
  try {
    const apiKey = process.env.GEMINI_API_KEY
    if (!apiKey) {
      return NextResponse.json(
        { error: "Missing GEMINI_API_KEY. Add it to .env.local and restart." },
        { status: 500 }
      )
    }

    const prompt = `Please provide an approximate global market share breakdown (in percentages) for the retinal imaging market market among the following companies: Zeiss, Canon, Optovue, Heidelberg, Topcon, Optos, Nidek, and Others. I need the output as a list with each company’s estimated percentage value, making sure the total adds up to 100%. The response should only include numbers with company names, suitable for creating a pie chart`

    const genAI = new GoogleGenerativeAI(apiKey)
    const preferredModel = process.env.GEMINI_MODEL
    const candidateModels = [preferredModel, "gemini-2.5-flash"].filter(Boolean) as string[]
    let raw = ""
    let lastErr: any = null

    for (const m of candidateModels) {
      try {
        const model = genAI.getGenerativeModel({ model: m })
        const res = await model.generateContent([{ text: prompt }])
        raw = res.response.text() || ""
        if (raw) break
      } catch (e: any) {
        lastErr = e
        continue
      }
    }

    if (!raw) {
      return NextResponse.json(
        { error: lastErr?.message || "Model failed to return a response." },
        { status: 500 }
      )
    }

    // Try parse JSON code fence first
    let parsedMap: Record<string, number> | null = null
    const fence = raw.match(/```json\s*([\s\S]*?)```/i)
    if (fence) {
      try {
        const j = JSON.parse(fence[1])
        if (Array.isArray(j)) {
          const m: Record<string, number> = {}
          for (const it of j) {
            if (it && typeof it.name === "string" && typeof it.value === "number") {
              m[it.name] = it.value
            } else if (Array.isArray(it) && it.length >= 2) {
              const [k, v] = it
              if (typeof k === "string" && typeof v === "number") m[k] = v
            }
          }
          parsedMap = m
        } else if (j && typeof j === "object") {
          const m: Record<string, number> = {}
          for (const [k, v] of Object.entries(j)) {
            const num = Number(v as any)
            if (!isNaN(num)) m[k] = num
          }
          parsedMap = m
        }
      } catch {
        // fallthrough to text parsing
      }
    }

    if (!parsedMap) {
      parsedMap = parseListTextToMap(raw)
    }

    if (!parsedMap || Object.keys(parsedMap).length === 0) {
      return NextResponse.json({ error: "Model returned an unparseable response." }, { status: 502 })
    }

    const distribution = coalesceToCompanies(parsedMap)
    const payload: DistPayload = { distribution, updatedAt: new Date().toISOString() }
    await writePersisted(payload)

    return NextResponse.json(payload)
  } catch (err: any) {
    return NextResponse.json({ error: err?.message || "Failed to generate market share" }, { status: 500 })
  }
}