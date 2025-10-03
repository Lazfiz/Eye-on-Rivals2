
import { NextResponse } from "next/server"
import { promises as fs } from "fs"
import path from "path"
import { GoogleGenerativeAI } from "@google/generative-ai"

export const runtime = "nodejs"

type CompanyRow = {
  name: string
  revenueUSD: number
  products: number
  patents: number
}

type StatsPayload = {
  companies: CompanyRow[]
  updatedAt: string
}

const STORAGE = path.join(process.cwd(), "backend", "retinal-stats.json")
const COMPANIES = ["Zeiss", "Canon", "Optovue", "Topcon", "Nidek"]

function normalizeCompany(raw: string): string | null {
  const s = (raw || "").trim().toLowerCase()
  if (!s) return null
  if (/(carl\s+)?zeiss/.test(s) || /meditec/.test(s)) return "Zeiss"
  if (/canon/.test(s)) return "Canon"
  if (/opto\s*vue|optovue/.test(s)) return "Optovue"
  if (/topcon/.test(s)) return "Topcon"
  if (/nidek/.test(s)) return "Nidek"
  return null
}

function parseMoneyToUSD(val: string): number {
  if (!val) return 0
  let s = val.replace(/[, ]+/g, "").replace(/\$/g, "").toLowerCase()
  // Handle suffixes
  let mult = 1
  if (s.endsWith("k")) { mult = 1_000; s = s.slice(0, -1) }
  else if (s.endsWith("m")) { mult = 1_000_000; s = s.slice(0, -1) }
  else if (s.endsWith("b")) { mult = 1_000_000_000; s = s.slice(0, -1) }
  else if (s.endsWith("t")) { mult = 1_000_000_000_000; s = s.slice(0, -1) }
  const n = Number(s.match(/-?\d+(\.\d+)?/)?.[0] ?? "0")
  if (!isFinite(n)) return 0
  return Math.round(n * mult)
}

function parseIntSafe(val: string): number {
  if (!val) return 0
  const n = Number((val.match(/-?\d+(\.\d+)?/) ?? [])[0] ?? "0")
  return isFinite(n) ? Math.round(n) : 0
}

function tryParseJSONFence(raw: string): CompanyRow[] | null {
  const fence = raw.match(/```json\s*([\s\S]*?)```/i)
  if (!fence) return null
  try {
    const j = JSON.parse(fence[1])
    const out: CompanyRow[] = []
    if (Array.isArray(j)) {
      for (const row of j) {
        if (!row) continue
        const name = normalizeCompany(String((row.name ?? row.company ?? row.Company) || ""))
        if (!name) continue
        const revenue = parseMoneyToUSD(String(row.revenueUSD ?? row.revenue ?? row.Revenue ?? "0"))
        const products = parseIntSafe(String(row.products ?? row.Products ?? "0"))
        const patents = parseIntSafe(String(row.patents ?? row.Patents ?? "0"))
        out.push({ name, revenueUSD: revenue, products, patents })
      }
      return out.length ? out : null
    } else if (j && typeof j === "object") {
      // Object keyed by company
      for (const [k, v] of Object.entries(j)) {
        const name = normalizeCompany(k)
        if (!name || !v || typeof v !== "object") continue
        const row: any = v
        const revenue = parseMoneyToUSD(String(row.revenueUSD ?? row.revenue ?? row.Revenue ?? "0"))
        const products = parseIntSafe(String(row.products ?? row.Products ?? "0"))
        const patents = parseIntSafe(String(row.patents ?? row.Patents ?? "0"))
        out.push({ name, revenueUSD: revenue, products, patents })
      }
      return out.length ? out : null
    }
    return null
  } catch {
    return null
  }
}

function tryParseMarkdownTable(raw: string): CompanyRow[] | null {
  const lines = raw.split(/\r?\n/).map(l => l.trim()).filter(Boolean)
  const tableLines = lines.filter(l => /\|/.test(l))
  if (tableLines.length < 2) return null

  // Find header and separator
  const headerIdx = tableLines.findIndex(l => /\|/g.test(l))
  if (headerIdx < 0 || headerIdx + 1 >= tableLines.length) return null
  const header = tableLines[headerIdx].split("|").map(s => s.trim().toLowerCase())
  const sep = tableLines[headerIdx + 1]
  if (!/^[:\-\|\s]+$/.test(sep)) {
    // some models might skip separator; allow anyway
  }

  // Identify columns
  const colIndex = {
    company: header.findIndex(h => /company|name/i.test(h)),
    revenue: header.findIndex(h => /revenue|usd/i.test(h)),
    products: header.findIndex(h => /product/i.test(h)),
    patents: header.findIndex(h => /patent/i.test(h)),
  }
  if (colIndex.company < 0) return null

  const out: CompanyRow[] = []
  for (let i = headerIdx + 1; i < tableLines.length; i++) {
    const rowLine = tableLines[i]
    if (!/\|/.test(rowLine)) continue
    const parts = rowLine.split("|").map(s => s.trim())
    const nameRaw = parts[colIndex.company] ?? ""
    const name = normalizeCompany(nameRaw)
    if (!name) continue

    const revenueStr = colIndex.revenue >= 0 ? (parts[colIndex.revenue] ?? "") : ""
    const productsStr = colIndex.products >= 0 ? (parts[colIndex.products] ?? "") : ""
    const patentsStr = colIndex.patents >= 0 ? (parts[colIndex.patents] ?? "") : ""

    const revenueUSD = parseMoneyToUSD(revenueStr)
    const products = parseIntSafe(productsStr)
    const patents = parseIntSafe(patentsStr)

    out.push({ name, revenueUSD, products, patents })
  }
  return out.length ? out : null
}

function tryParseLooseList(raw: string): CompanyRow[] | null {
  // Fallback: lines like "Zeiss: revenue $1.2B, products 12, patents 300"
  const lines = raw.split(/\r?\n/).map(l => l.trim()).filter(Boolean)
  const out: CompanyRow[] = []
  for (const l of lines) {
    const m = l.match(/^[-*\u2022]?\s*([^:]+):\s*(.+)$/)
    if (!m) continue
    const name = normalizeCompany(m[1])
    if (!name) continue
    const rest = m[2]
    const revenue = rest.match(/revenue[^$€£]*([$€£]?[0-9.,]+[kmbtKMBT]?)/i)?.[1] ?? ""
    const products = rest.match(/product[^0-9]*([0-9]+)/i)?.[1] ?? ""
    const patents = rest.match(/patent[^0-9]*([0-9]+)/i)?.[1] ?? ""
    out.push({
      name,
      revenueUSD: parseMoneyToUSD(revenue),
      products: parseIntSafe(products),
      patents: parseIntSafe(patents),
    })
  }
  return out.length ? out : null
}

function coalesceCompanies(rows: CompanyRow[]): CompanyRow[] {
  // Keep only target companies and reduce duplicates
  const map = new Map<string, CompanyRow>()
  for (const r of rows) {
    if (!COMPANIES.includes(r.name)) continue
    const prev = map.get(r.name)
    if (!prev) {
      map.set(r.name, r)
    } else {
      // Prefer non-zero values; otherwise keep existing
      map.set(r.name, {
        name: r.name,
        revenueUSD: r.revenueUSD || prev.revenueUSD,
        products: r.products || prev.products,
        patents: r.patents || prev.patents,
      })
    }
  }
  // Ensure every company exists (fill zeros if missing)
  for (const c of COMPANIES) {
    if (!map.has(c)) map.set(c, { name: c, revenueUSD: 0, products: 0, patents: 0 })
  }
  return Array.from(map.values())
}

async function readPersisted(): Promise<StatsPayload | null> {
  try {
    const raw = await fs.readFile(STORAGE, "utf-8")
    const json = JSON.parse(raw)
    if (Array.isArray(json?.companies)) {
      return json as StatsPayload
    }
    return null
  } catch {
    return null
  }
}

async function writePersisted(payload: StatsPayload) {
  await fs.mkdir(path.dirname(STORAGE), { recursive: true })
  await fs.writeFile(STORAGE, JSON.stringify(payload, null, 2), "utf-8")
}

export async function GET() {
  try {
    const existing = await readPersisted()
    if (existing) return NextResponse.json(existing)
    return NextResponse.json({ companies: [], updatedAt: null })
  } catch (err: any) {
    return NextResponse.json({ error: err?.message || "Failed to read retinal stats" }, { status: 500 })
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

    const prompt = `Please provide an approximate breakdown for the retinal imaging market across the following companies: Zeiss, Canon, Optovue, Topcon, and Nidek. For each company, include:

Estimated revenue from retinal imaging (USD, approximate, using medical/vision-care division revenue where necessary).

Approximate number of retinal imaging products they currently offer.

Approximate number of active or granted patents related to retinal imaging.

Important: I need a single best estimate number for each category (not a range). Present the answer in a clear tabular format with one row per company. If exact numbers are not available, provide the most reasonable single-point estimate based on available market information.`

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

    // Try parsers in order: JSON code fence, Markdown table, loose list
    let rows =
      tryParseJSONFence(raw) ||
      tryParseMarkdownTable(raw) ||
      tryParseLooseList(raw)

    if (!rows || rows.length === 0) {
      return NextResponse.json({ error: "Model returned an unparseable response." }, { status: 502 })
    }

    // Normalize to target companies and ensure each exists
    const companies = coalesceCompanies(rows)
    const payload: StatsPayload = { companies, updatedAt: new Date().toISOString() }
    await writePersisted(payload)
    return NextResponse.json(payload)
  } catch (err: any) {
    return NextResponse.json({ error: err?.message || "Failed to generate retinal stats" }, { status: 500 })
  }
}