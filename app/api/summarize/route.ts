import { NextResponse } from "next/server"
import { GoogleGenerativeAI } from "@google/generative-ai"

export const runtime = "nodejs"

type ReqBody = {
  urls: string[]
  companyName?: string
}

function stripHtml(html: string): string {
  return html
    .replace(/<script[^>]*>[\s\S]*?<\/script>/gi, " ")
    .replace(/<style[^>]*>[\s\S]*?<\/style>/gi, " ")
    .replace(/<script[^>]*>[\s\S]*?<\/script>/gi, " ")
    .replace(/<style[^>]*>[\s\S]*?<\/style>/gi, " ")
    .replace(/<[^>]+>/g, " ")
    .replace(/\s+/g, " ")
    .trim()
}

export async function POST(req: Request) {
  try {
    const apiKey = process.env.GEMINI_API_KEY
    if (!apiKey) {
      return NextResponse.json(
        { error: "Missing GEMINI_API_KEY. Create .env.local with GEMINI_API_KEY=<your_key> and restart the dev server." },
        { status: 500 }
      )
    }

    const body = (await req.json().catch(() => ({}))) as ReqBody
    if (!Array.isArray(body.urls) || body.urls.length === 0) {
      return NextResponse.json({ error: "No URLs provided." }, { status: 400 })
    }

    // Fetch article pages on the server and extract readable text
    const texts = await Promise.all(
      body.urls.map(async (url) => {
        try {
          const res = await fetch(url, {
            // Some sites are picky about UA
            headers: { "User-Agent": "EyeOnRivalsBot/1.0 (+https://example.com)" },
          })
          const html = await res.text()
          const text = stripHtml(html).slice(0, 20000) // limit per-article text
          return text
        } catch {
          return ""
        }
      })
    )

    const combined = texts.filter(Boolean).join("\n\n---\n\n")
    if (!combined) {
      return NextResponse.json({ error: "Failed to fetch any article content." }, { status: 502 })
    }

    const genAI = new GoogleGenerativeAI(apiKey)
    const preferredModel = process.env.GEMINI_MODEL
    const candidateModels = [preferredModel, "gemini-2.5-flash"].filter(Boolean) as string[]
    
    const prompt = `
You are a senior market analyst. Based on the following recent news articles about ${body.companyName ?? "the company"},
produce:
1) An executive summary (120–180 words)
2) 3–5 concise bullet key takeaways
3) A short Risks & Opportunities note (2–3 sentences)
Be specific, avoid generic phrases, and reflect only what is supported by the articles.
`

    let lastErr: any = null
    for (const m of candidateModels) {
      try {
        const model = genAI.getGenerativeModel({ model: m })
        const result = await model.generateContent([{ text: prompt }, { text: combined }])
        const summary = result.response.text()
        return NextResponse.json({ summary, model: m })
      } catch (e: any) {
        const msg = e?.message || ""
        // If model not found/unsupported, try the next one
        if (e?.status === 404 || /not found|unsupported|ListModels/i.test(msg)) {
          lastErr = e
          continue
        }
        // Other errors: return immediately
        return NextResponse.json({ error: msg || "Summarization failed." }, { status: 500 })
      }
    }
    
    return NextResponse.json(
      {
        error:
          lastErr?.message ||
          "All candidate models failed. Set GEMINI_MODEL in .env.local to a supported model (e.g., gemini-1.5-pro-latest).",
      },
      { status: 500 }
    )
  } catch (error: any) {
    return NextResponse.json({ error: error?.message ?? "Summarization failed." }, { status: 500 })
  }
}