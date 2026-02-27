import { NextResponse } from "next/server"
import { promises as fs } from "fs"
import path from "path"

export const runtime = "nodejs"

type Patent = { Title: string; Date: string; URL: string }
type OutputFile = {
  Competitor?: Array<{
    Name?: string
    Patents?: Array<Record<string, unknown>>
  }>
}

export async function GET() {
  const patentsByCompany: Record<string, Patent[]> = {
    Zeiss: [],
    Canon: [],
    Topcon: [],
    Optovue: [],
    Nidek: [],
  }

  try {
    const filePath = path.join(process.cwd(), "backend", "outputData.json")
    const json = await fs.readFile(filePath, "utf-8")
    const data = JSON.parse(json) as OutputFile
    const rows = Array.isArray(data?.Competitor) ? data.Competitor : []

    const normalizeKey = (name: string): keyof typeof patentsByCompany | null => {
      const s = (name || "").trim().toLowerCase()
      if (s === "zeiss") return "Zeiss"
      if (s === "canon") return "Canon"
      if (s === "topcon") return "Topcon"
      if (s === "optovue") return "Optovue"
      if (s === "nidek") return "Nidek"
      return null
    }

    for (const row of rows) {
      const key = normalizeKey(String(row?.Name || ""))
      if (!key) continue
      const rawPatents = Array.isArray(row?.Patents) ? row.Patents : []
      const items: Patent[] = rawPatents
        .map((p: any) => ({
          Title: p?.Title ?? "",
          Date: p?.Date ?? "",
          URL: p?.URL ?? "",
        }))
        .filter((p: Patent) => Boolean(p.Title) && Boolean(p.URL))
      patentsByCompany[key] = items
    }
  } catch {
    // keep empty defaults
  }

  return NextResponse.json({ patentsByCompany })
}
