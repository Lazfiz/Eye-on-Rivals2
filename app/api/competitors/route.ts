import { NextResponse } from "next/server"
import { promises as fs } from "fs"
import path from "path"

export const runtime = "nodejs"

type NewsItem = { Date: string; Headline: string; URL: string }
type JobItem = { Date: string; "Job Title": string; URL: string }
type WhitePaper = { Date: string; Title: string; Abstract: string; URL: string }
type Patent = { Date: string; Title: string; Abstract: string; URL: string }

type Competitor = {
  Name: string
  News: NewsItem[]
  "Job Listings": JobItem[]
  "White Papers": WhitePaper[]
  Patents: Patent[]
}

type ApiData = { Competitor: Competitor[] }

export async function GET() {
  try {
    const filePath = path.join(process.cwd(), "backend", "DummyJson.json")
    const content = await fs.readFile(filePath, "utf-8")
    const data: ApiData = JSON.parse(content)
    return NextResponse.json(data)
  } catch (error: any) {
    return NextResponse.json({ error: error?.message ?? "Failed to load data" }, { status: 500 })
  }
}