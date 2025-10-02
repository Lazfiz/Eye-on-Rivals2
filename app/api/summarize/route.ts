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

async function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

async function generateWithRetry(model: any, prompt: string, combined: string) {
  let lastErr: any = null
  const delays = [500, 1000, 2000] // exponential-ish backoff
  for (let i = 0; i < delays.length; i++) {
    try {
      const result = await model.generateContent([{ text: prompt }, { text: combined }])
      const raw = result.response.text() || ""
      return raw
    } catch (e: any) {
      const msg = e?.message || ""
      // Retry on transient overloads
      if (e?.status === 503 || /overloaded|Service Unavailable/i.test(msg)) {
        lastErr = e
        await sleep(delays[i])
        continue
      }
      // Non-retryable error
      throw e
    }
  }
  throw lastErr || new Error("Model overloaded; retries exhausted")
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
 You are a concise market analyst. Using ONLY the content below about ${body.companyName ?? "the company"}, write a tweet-length update:
 - Output EXACTLY 3 bullet points (or fewer if there is not enough evidence)
 - Total length MUST be ≤ 280 characters (all bullets combined)
 - Each bullet must be short, specific, and supported by the articles
 - No title/preface, no hashtags, no emojis, no links, no filler, no speculation
 `

    let lastErr: any = null
    for (const m of candidateModels) {
      try {
        const model = genAI.getGenerativeModel({ model: m })
        const raw = await generateWithRetry(model, prompt, combined)

        // Post-process: keep up to 3 concise bullets and ensure <= 280 chars total
        const bullets = raw
          .split(/\r?\n/)
          .map((s: string) => s.trim())
          .filter(Boolean)
          .map((s: string) => s.replace(/^[\-\*\u2022]\s*/, "")) // strip leading bullet markers like -, *, •
          .filter((s: string) => s.length > 0)
          .slice(0, 3)

        function joinBullets(parts: string[]) {
          return parts.join("\n")
        }

        let out = joinBullets(bullets)

        if (out.length > 280) {
          // Try trimming the 3rd bullet first
          const first = bullets[0] ?? ""
          let second = bullets[1] ?? ""
          let third = bullets[2] ?? ""

          // Trim third until it fits or drop it
          while ((joinBullets([first, second, third]).length > 280) && third.length > 0) {
            third = third.slice(0, Math.max(0, third.length - 5)).trimEnd()
          }
          let candidate = third ? joinBullets([first, second, third]) : joinBullets([first, second])

          // If still too long, trim second as well
          if (candidate.length > 280) {
            while ((joinBullets([first, second]).length > 280) && second.length > 0) {
              second = second.slice(0, Math.max(0, second.length - 5)).trimEnd()
            }
            candidate = joinBullets([first, second]).trim()
          }

          // If still too long, fall back to just first (trimmed)
          if (candidate.length > 280) {
            let firstTrim = first
            while (firstTrim.length > 280) {
              firstTrim = firstTrim.slice(0, Math.max(0, firstTrim.length - 5)).trimEnd()
            }
            candidate = firstTrim
          }

          out = candidate
        }

        return NextResponse.json({ summary: out, model: m })
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