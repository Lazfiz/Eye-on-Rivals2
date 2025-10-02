import { NextResponse } from "next/server"
import { promises as fs } from "fs"
import path from "path"

export const runtime = "nodejs"

type Patent = { Title: string; Date: string; URL: string }
type PatentFile = { patents: (Patent & Record<string, unknown>)[] }

export async function GET() {
  const mapping = [
    { key: "Zeiss", filename: "zeiss_patents.json" },
    { key: "Canon", filename: "canon_patents.json" },
    { key: "Topcon", filename: "topcon_patents.json" },
    { key: "Optovue", filename: "optovue_patents.json" },
    { key: "Nidek", filename: "nidek_patents.json" },
  ] as const

  const patentsByCompany: Record<string, Patent[]> = {}

  await Promise.all(
    mapping.map(async ({ key, filename }) => {
      try {
        const filePath = path.join(process.cwd(), "backend", filename)
        const json = await fs.readFile(filePath, "utf-8")
        const data: PatentFile = JSON.parse(json)
        const items: Patent[] =
          Array.isArray((data as any).patents)
            ? (data as any).patents.map((p: any) => ({
                Title: p?.Title ?? "",
                Date: p?.Date ?? "",
                URL: p?.URL ?? "",
              })).filter((p: Patent) => p.Title && p.Date && p.URL)
            : []
        patentsByCompany[key] = items
      } catch {
        patentsByCompany[key] = []
      }
    })
  )

  return NextResponse.json({ patentsByCompany })
}