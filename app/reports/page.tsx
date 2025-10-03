"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { FileText, RefreshCcw } from "lucide-react"

type NewsItem = { Date: string; Headline: string; URL: string }
type JobItem = { Date: string; "Job Title": string; URL: string }
type WhitePaper = { Date: string; Title: string; Abstract: string; URL: string }
type Patent = { Date: string; Title: string; Abstract: string; URL: string }

type CompetitorJson = {
  Name: string
  News: NewsItem[]
  "Job Listings": JobItem[]
  "White Papers": WhitePaper[]
  Patents: Patent[]
}

type ApiData = { Competitor: CompetitorJson[] }

const TARGET_COMPETITORS = ["Zeiss", "Topcon", "Nidek", "Canon", "Optovue"]

export default function ReportsPage() {
  const [data, setData] = useState<CompetitorJson[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [summaries, setSummaries] = useState<Record<string, { text: string; model?: string } | null>>({})
  const [updatedAt, setUpdatedAt] = useState<string | null>(null)

  useEffect(() => {
    fetch("/api/competitors")
      .then((r) => r.json())
      .then((json: ApiData) => setData(json?.Competitor ?? []))
      .catch(() => setData([]))
  }, [])

  // Load persisted summaries (if any)
  useEffect(() => {
    fetch("/api/summaries")
      .then((r) => r.json())
      .then((json) => {
        if (json?.summaries) setSummaries(json.summaries)
        if (json?.updatedAt) setUpdatedAt(json.updatedAt)
      })
      .catch(() => {
        // ignore, start with empty summaries
      })
  }, [])

  function findByName(name: string): CompetitorJson | undefined {
    const lower = name.toLowerCase()
    return data.find((c) => c.Name.toLowerCase().includes(lower))
  }

  function newsUrls(name: string): { urls: string[]; count: number } {
    const comp = findByName(name)
    const list = (comp?.News ?? []).slice(0, 5)
    const urls = list.map((n) => n.URL).filter(Boolean)
    return { urls, count: list.length }
  }

  async function summarizeAll() {
    try {
      setLoading(true)
      setError(null)
      const updates: Record<string, { text: string; model?: string } | null> = {}

      await Promise.all(
        TARGET_COMPETITORS.map(async (name) => {
          const { urls } = newsUrls(name)
          if (urls.length === 0) {
            updates[name] = { text: "No news available to summarize." }
            return
          }
          try {
            const res = await fetch("/api/summarize", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ urls, companyName: name }),
            })
            const json = await res.json()
            if (!res.ok) {
              updates[name] = { text: json?.error || "Failed to summarize." }
              return
            }
            updates[name] = { text: json.summary || "No summary returned.", model: json.model }
          } catch (e: any) {
            updates[name] = { text: e?.message || "Failed to summarize." }
          }
        })
      )

      // Persist summaries to backend
      try {
        const saveRes = await fetch("/api/summaries", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ summaries: updates }),
        })
        const saved = await saveRes.json()
        if (saveRes.ok) {
          setSummaries(saved.summaries ?? updates)
          setUpdatedAt(saved.updatedAt ?? new Date().toISOString())
        } else {
          setSummaries(updates)
          setError(saved?.error || "Failed to save summaries, using in-memory results.")
        }
      } catch (err: any) {
        setSummaries(updates)
        setError(err?.message || "Failed to save summaries, using in-memory results.")
      }
    } catch (e: any) {
      setError(e?.message || "Failed to update summaries.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b backdrop-blur-sm sticky top-0 z-40" style={{ backgroundColor: "#2E5A87" }}>
        <div className="container mx-auto px-4 py-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <img src="/optos-logo.webp" alt="Optos Logo" className="w-24 h-24 object-contain" />
              <div>
                <h1 className="text-xl font-bold text-white">Eye on Rivals</h1>
                <p className="text-sm text-white/80">Reports</p>
              </div>
            </div>
            <nav className="hidden md:flex items-center space-x-6">
              <Link href="/" className="text-white hover:text-white/80 transition-colors">
                Dashboard
              </Link>
              <a href="#competitors" className="text-white/70 cursor-not-allowed">Competitors</a>
              <a href="#insights" className="text-white/70 cursor-not-allowed">Insights</a>
              <Link href="/reports" className="text-white underline underline-offset-4">Reports</Link>
            </nav>
            <div className="flex flex-col items-end">
              <Button
                size="sm"
                onClick={summarizeAll}
                className="bg-white text-blue-800 hover:bg-white/90"
                disabled={loading}
              >
                <RefreshCcw className="w-4 h-4 mr-2" />
                {loading ? "Updating..." : "Update"}
              </Button>
              <span className="mt-1 text-xs text-white/80">
                {updatedAt ? `Last updated: ${new Date(updatedAt).toLocaleString()}` : "No saved summaries yet"}
              </span>
            </div>
          </div>
        </div>
      </header>

      <main className="py-12">
        <div className="container mx-auto px-4">
          {error && (
            <div className="mb-6 p-3 rounded border border-red-200 bg-red-50 text-red-700">{error}</div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-6">
            {TARGET_COMPETITORS.map((name) => {
              const { urls, count } = newsUrls(name)
              const summary = summaries[name]
              const comp = findByName(name)
              return (
                <Card key={name} className="border-2 border-blue-200">
                  <CardHeader>
                    <CardTitle className="text-blue-600 flex items-center">
                      <FileText className="w-5 h-5 mr-2" />
                      {name}
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <div className="text-sm text-blue-600/80">
                      Latest news items: {count} {count > 0 ? `(showing up to 5)` : ""}
                    </div>
                    {comp && comp.News && comp.News.length > 0 && (
                      <ul className="space-y-1">
                        {comp.News.slice(0, 5).map((n, idx) => (
                          <li key={idx} className="text-sm">
                            <a href={n.URL} target="_blank" rel="noopener noreferrer" className="text-blue-600 underline">
                              {n.Headline}
                            </a>
                            <span className="text-xs text-blue-600/60 ml-2">{n.Date}</span>
                          </li>
                        ))}
                      </ul>
                    )}
                    <div className="p-3 rounded border border-blue-200 bg-blue-50 text-blue-700 whitespace-pre-wrap min-h-24">
                      {loading && !summary ? "Waiting..." : summary?.text || "No summary yet. Press Update."}
                    </div>
                    {summary?.model && (
                      <div className="text-[11px] text-blue-600/60">Model: {summary.model}</div>
                    )}
                  </CardContent>
                </Card>
              )
            })}
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="py-2" style={{ backgroundColor: "#2E5A87" }}>
        <div className="container mx-auto px-4">
          <div className="flex flex-col md:flex-row justify-between items-center">
            <div className="flex items-center space-x-3 mb-4 md:mb-0">
              <img src="/optos-logo.webp" alt="Optos Logo" className="w-24 h-24 object-contain" />
              <span className="text-lg font-semibold text-white">Eye on Rivals</span>
            </div>
            <div className="flex space-x-6 text-sm text-white/80">
              <a href="#" className="hover:text-white transition-colors">
                Privacy
              </a>
              <a href="#" className="hover:text-white transition-colors">
                Terms
              </a>
              <a href="#" className="hover:text-white transition-colors">
                Support
              </a>
              <a href="#" className="hover:text-white transition-colors">
                Contact
              </a>
            </div>
          </div>
          <div className="mt-8 pt-8 border-t border-white/20 text-center text-sm text-white/80">
            <p>&copy; 2025 Eye on Rivals. Powered by Optos. All rights reserved.</p>
          </div>
        </div>
      </footer>
    </div>
  )
}