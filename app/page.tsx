"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import {
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
} from "recharts"
import {
  TrendingUp,
  Users,
  FileText,
  Briefcase,
  Zap,
  Target,
  Activity,
  Gamepad2,
  Star,
  Award,
  Flame,
  RefreshCcw,
} from "lucide-react"
import Link from "next/link"

const competitors = [
  {
    id: 1,
    name: "Zeiss",
    threatScore: 85,
    marketShare: 22, // Reduced from 28 to accommodate Optos
    recentActivity: "High",
    products: 47,
    patents: 234,
    employees: 32000,
    revenue: "7.5B",
    color: "bg-blue-500",
    // Pokemon-style stats
    level: 42,
    hp: 850,
    maxHp: 1000,
    attack: 92,
    defense: 78,
    speed: 65,
    special: 88,
    type: "Tech Giant",
    rarity: "Legendary",
    abilities: ["Innovation Boost", "Patent Shield", "Market Dominance"],
    weaknesses: ["Regulatory Pressure", "New Entrants"],
    strengths: ["R&D Investment", "Brand Recognition", "Global Reach"],
    battleCry: "Precision is our power!",
    element: "⚡",
  },
  {
    id: 2,
    name: "Topcon",
    threatScore: 72,
    marketShare: 18, // Reduced from 22 to accommodate Optos
    recentActivity: "Medium",
    products: 38,
    patents: 189,
    employees: 5200,
    revenue: "1.2B",
    color: "bg-green-500",
    level: 35,
    hp: 720,
    maxHp: 850,
    attack: 75,
    defense: 82,
    speed: 78,
    special: 71,
    type: "Specialist",
    rarity: "Rare",
    abilities: ["Precision Strike", "Adaptive Tech", "Market Agility"],
    weaknesses: ["Limited Resources", "Scale Constraints"],
    strengths: ["Specialized Focus", "Innovation Speed", "Customer Loyalty"],
    battleCry: "Precision meets innovation!",
    element: "🌿",
  },
  {
    id: 3,
    name: "Nidek",
    threatScore: 68,
    marketShare: 15, // Reduced from 18 to accommodate Optos
    recentActivity: "Medium",
    products: 31,
    patents: 156,
    employees: 2800,
    revenue: "890M",
    color: "bg-yellow-500",
    level: 32,
    hp: 680,
    maxHp: 800,
    attack: 68,
    defense: 75,
    speed: 72,
    special: 69,
    type: "Innovator",
    rarity: "Uncommon",
    abilities: ["Tech Evolution", "Cost Efficiency", "Rapid Development"],
    weaknesses: ["Market Reach", "Brand Recognition"],
    strengths: ["Product Quality", "Price Competitiveness", "Technical Expertise"],
    battleCry: "Innovation never stops!",
    element: "⚡",
  },
  {
    id: 4,
    name: "Canon",
    threatScore: 91,
    marketShare: 20, // Reduced from 35 to accommodate Optos
    recentActivity: "Very High",
    products: 52,
    patents: 312,
    employees: 180000,
    revenue: "31.9B",
    color: "bg-red-500",
    level: 48,
    hp: 910,
    maxHp: 1200,
    attack: 95,
    defense: 88,
    speed: 70,
    special: 92,
    type: "Mega Corp",
    rarity: "Mythical",
    abilities: ["Market Crusher", "Resource Abundance", "Global Network"],
    weaknesses: ["Bureaucracy", "Slow Adaptation"],
    strengths: ["Massive Scale", "Financial Power", "Diverse Portfolio"],
    battleCry: "Domination through excellence!",
    element: "🔥",
  },
  {
    id: 5,
    name: "Optovue",
    threatScore: 64,
    marketShare: 5, // Reduced from 15 to accommodate Optos
    recentActivity: "Low",
    products: 24,
    patents: 98,
    employees: 850,
    revenue: "180M",
    color: "bg-purple-500",
    level: 28,
    hp: 640,
    maxHp: 750,
    attack: 64,
    defense: 70,
    speed: 85,
    special: 78,
    type: "Niche Expert",
    rarity: "Common",
    abilities: ["Specialized Knowledge", "Agile Response", "Quality Focus"],
    weaknesses: ["Limited Scale", "Resource Constraints"],
    strengths: ["Deep Expertise", "Customer Relationships", "Flexibility"],
    battleCry: "Excellence in every detail!",
    element: "💜",
  },
]

// Helper to parse date string and get month
function parseDateMonth(dateStr: string): number {
  // Handle DD/MM/YYYY format
  if (dateStr.includes('/')) {
    const parts = dateStr.split('/')
    if (parts.length === 3) {
      const day = parseInt(parts[0])
      const month = parseInt(parts[1]) - 1 // 0-11
      const year = parseInt(parts[2])
      return year === 2025 ? month : -1
    }
  }
  return -1
}

// Helper to generate trend data for 2025
function generateTrendData(companyData: CompanyData[]) {
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
  const currentMonth = new Date().getMonth() // 0-11
  const data = []
  
  // Initialize counts for each month
  const monthlyJobCounts = new Array(12).fill(0)
  const monthlyPatentCounts = new Array(12).fill(0)
  const monthlyPressCounts = new Array(12).fill(0)
  
  // Count jobs per month (distribute evenly since we don't have actual dates)
  companyData.forEach(company => {
    if (company.Jobs && company.Jobs.length > 0) {
      const jobsPerMonth = Math.ceil(company.Jobs.length / (currentMonth + 1))
      
      for (let i = 0; i <= currentMonth; i++) {
        const remainingJobs = company.Jobs.length - (i * jobsPerMonth)
        const jobsToAdd = Math.min(jobsPerMonth, Math.max(0, remainingJobs))
        monthlyJobCounts[i] += jobsToAdd
      }
    }
  })
  
  // Count patents per month using actual dates
  companyData.forEach(company => {
    if (company.patents && company.patents.length > 0) {
      company.patents.forEach(patent => {
        if (patent.Date) {
          const month = parseDateMonth(patent.Date)
          if (month >= 0 && month <= currentMonth) {
            monthlyPatentCounts[month]++
          }
        }
      })
    }
  })
  
  // Count press releases per month using actual dates
  companyData.forEach(company => {
    if (company.news && company.news.length > 0) {
      company.news.forEach(pressRelease => {
        if (pressRelease.Date) {
          const month = parseDateMonth(pressRelease.Date)
          if (month >= 0 && month <= currentMonth) {
            monthlyPressCounts[month]++
          }
        }
      })
    }
  })
  
  // Generate trend data up to current month
  for (let i = 0; i <= currentMonth; i++) {
    data.push({
      month: months[i],
      jobPostings: monthlyJobCounts[i],
      patents: monthlyPatentCounts[i],
      pressReleases: monthlyPressCounts[i],
    })
  }
  
  return data
}

const MARKET_COLORS: Record<string, string> = {
  Zeiss: "#2563eb",       // blue
  Topcon: "#10b981",      // green
  Canon: "#ef4444",       // red
  Nidek: "#f59e0b",       // amber
  Optovue: "#8b5cf6",     // purple
  Optos: "#1d4ed8",       // deep blue
  Heidelberg: "#14b8a6",  // teal
  Others: "#9ca3af",      // gray
}

// Fallback static distribution if backend file not yet generated
const fallbackMarketShare = [
  { name: "Optos", value: 40 },
  { name: "Zeiss", value: 22 },
  { name: "Topcon", value: 18 },
  { name: "Nidek", value: 15 },
  { name: "Canon", value: 20 },
  { name: "Optovue", value: 5 },
]

// This will be replaced by persisted distribution when available
let marketShareData: { name: string; value: number; color?: string }[] = fallbackMarketShare.map(d => ({
  ...d,
  color: MARKET_COLORS[d.name] || "#64748b",
}))

const COLORS = ["#2563eb", "#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6"]

type NewsItem = { Date: string; Headline: string; URL: string }
type JobItem = { Date: string; "Job Title": string; URL: string }
type WhitePaper = { Date: string; Title: string; Abstract: string; URL: string }
type Patent = { Date: string; Title: string; Abstract: string; URL: string }
type PatentLite = { Title: string; Date: string; URL: string }
type CompanyData = {
  name: string
  news: NewsItem[]
  jobListings: JobItem[]
  Jobs: JobItem[]
  whitePapers: WhitePaper[]
  patents: Patent[]
}

export default function EyeOnRivalsLanding() {
  const [selectedCompetitor, setSelectedCompetitor] = useState(competitors[0])
  const [gamifiedMode, setGamefiedMode] = useState(false)
  const [companyData, setCompanyData] = useState<CompanyData[]>([])
  const [patentsByCompany, setPatentsByCompany] = useState<Record<string, PatentLite[]>>({})
  const [isScraping, setIsScraping] = useState(false)
  const [scrapeMessage, setScrapeMessage] = useState("")
  const [showVideo, setShowVideo] = useState(false)

  // Market share state (persisted via /api/market-share)
  const [msData, setMsData] = useState<{ name: string; value: number }[]>([])
  const [msUpdatedAt, setMsUpdatedAt] = useState<string | null>(null)
  const [msLoading, setMsLoading] = useState(false)
  const [msError, setMsError] = useState<string | null>(null)

  // Retinal-imaging stats (persisted via /api/retinal-stats)
  const [rtStats, setRtStats] = useState<Record<string, { revenueUSD: number; products: number; patents: number }>>({})
  const [rtUpdatedAt, setRtUpdatedAt] = useState<string | null>(null)
  const [rtLoading, setRtLoading] = useState(false)
  const [rtError, setRtError] = useState<string | null>(null)
 
  useEffect(() => {
    let isMounted = true
    fetch("/api/competitors")
      .then((res) => res.json())
      .then((data) => {
        const mapped: CompanyData[] = (data?.Competitor ?? []).map((c: any) => ({
          name: c.Name,
          news: c.News ?? [],
          jobListings: c["Job Listings"] ?? [],
          Jobs: c.Jobs ?? [],
          whitePapers: c["White Papers"] ?? [],
          patents: c.Patents ?? [],
        }))
        if (isMounted) setCompanyData(mapped)
      })
      .catch((err) => console.error("Failed to load competitors", err))
    return () => {
      isMounted = false
    }
  }, [])

  // Load patents from dedicated JSON files per competitor
  useEffect(() => {
    let mounted = true
    fetch("/api/patents")
      .then((res) => res.json())
      .then((json) => {
        const map = (json?.patentsByCompany ?? {}) as Record<string, PatentLite[]>
        if (mounted) setPatentsByCompany(map)
      })
      .catch(() => {
        if (mounted) setPatentsByCompany({})
      })
    return () => {
      mounted = false
    }
  }, [])

  // Load persisted market share distribution (if any)
  useEffect(() => {
    let alive = true
    fetch("/api/market-share")
      .then((r) => r.json())
      .then((json) => {
        if (!alive) return
        if (Array.isArray(json?.distribution)) {
          setMsData(json.distribution)
        }
        if (json?.updatedAt) setMsUpdatedAt(json.updatedAt)
      })
      .catch(() => {
        // ignore
      })
    return () => {
      alive = false
    }
  }, [])
 
  // Load persisted retinal stats (if any)
  useEffect(() => {
    let alive = true
    fetch("/api/retinal-stats")
      .then((r) => r.json())
      .then((json) => {
        if (!alive) return
        const rows = Array.isArray(json?.companies) ? json.companies as { name: string; revenueUSD: number; products: number; patents: number }[] : []
        const map: Record<string, { revenueUSD: number; products: number; patents: number }> = {}
        rows.forEach((row) => {
          map[row.name.toLowerCase()] = { revenueUSD: row.revenueUSD || 0, products: row.products || 0, patents: row.patents || 0 }
        })
        setRtStats(map)
        if (json?.updatedAt) setRtUpdatedAt(json.updatedAt)
      })
      .catch(() => {
        // ignore
      })
    return () => { alive = false }
  }, [])

  // Helper to fetch patents for a competitor (case-insensitive)
  function getPatentsFor(name: string): PatentLite[] {
    const entries = Object.entries(patentsByCompany)
    const found = entries.find(([k]) => k.toLowerCase() === name.toLowerCase())
    return found ? found[1] : []
  }

  const selectedCompany = companyData.find(
    (c) => c.name.toLowerCase() === selectedCompetitor.name.toLowerCase()
  )
  
  // Generate trend data based on actual company data
  const trendData = generateTrendData(companyData)

  // If we have msData from backend, override marketShareData for the chart
  if (msData && msData.length) {
    marketShareData = msData.map((d) => ({
      ...d,
      color: MARKET_COLORS[d.name] || "#64748b",
    }))
  }
 
  // Handle scraper execution
  const handleStartMonitoring = async () => {
    setIsScraping(true)
    setShowVideo(true)
    setScrapeMessage("Starting data collection...")
    
    try {
      const response = await fetch('/api/scraper', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      })
      
      const result = await response.json()
      
      if (result.success) {
        setScrapeMessage(`Data collection completed successfully! Used ${result.pythonCommand || 'python'}. Refreshing data...`)
        // Hide video and refresh data after scraping
        setTimeout(() => {
          setShowVideo(false)
          setTimeout(() => {
            window.location.reload()
          }, 500)
        }, 1000)
      } else {
        setScrapeMessage(`Failed to collect data: ${result.message}${result.details ? ` - ${result.details}` : ''}`)
        setShowVideo(false)
      }
    } catch (error) {
      setScrapeMessage("Failed to start data collection. Please try again.")
      console.error('Scraper error:', error)
      setShowVideo(false)
    } finally {
      setIsScraping(false)
    }
  }

  // Update market share distribution via Gemini and persist to backend
  const updateMarketShare = async () => {
    setMsLoading(true)
    setMsError(null)
    try {
      const res = await fetch("/api/market-share", { method: "POST" })
      const json = await res.json()
      if (!res.ok) {
        throw new Error(json?.error || "Failed to update market share")
      }
      if (Array.isArray(json?.distribution)) setMsData(json.distribution)
      setMsUpdatedAt(json?.updatedAt || new Date().toISOString())
    } catch (e: any) {
      setMsError(e?.message || "Failed to update market share")
    } finally {
      setMsLoading(false)
    }
  }

  // Format revenue short, e.g., $1.2B
  const formatUSDShort = (n: number) => {
    if (!n || n <= 0) return "N/A"
    const abs = Math.abs(n)
    const sign = n < 0 ? "-" : ""
    if (abs >= 1_000_000_000_000) return `${sign}$${(abs / 1_000_000_000_000).toFixed(1)}T`
    if (abs >= 1_000_000_000) return `${sign}$${(abs / 1_000_000_000).toFixed(1)}B`
    if (abs >= 1_000_000) return `${sign}$${(abs / 1_000_000).toFixed(1)}M`
    if (abs >= 1_000) return `${sign}$${(abs / 1_000).toFixed(1)}K`
    return `${sign}$${abs.toFixed(0)}`
  }

  // Update retinal imaging stats via Gemini and persist to backend
  const updateRetinalStats = async () => {
    setRtLoading(true)
    setRtError(null)
    try {
      const res = await fetch("/api/retinal-stats", { method: "POST" })
      const json = await res.json()
      if (!res.ok) {
        throw new Error(json?.error || "Failed to update company stats")
      }
      const rows = Array.isArray(json?.companies) ? json.companies as { name: string; revenueUSD: number; products: number; patents: number }[] : []
      const map: Record<string, { revenueUSD: number; products: number; patents: number }> = {}
      rows.forEach((row) => {
        map[row.name.toLowerCase()] = { revenueUSD: row.revenueUSD || 0, products: row.products || 0, patents: row.patents || 0 }
      })
      setRtStats(map)
      setRtUpdatedAt(json?.updatedAt || new Date().toISOString())
    } catch (e: any) {
      setRtError(e?.message || "Failed to update company stats")
    } finally {
      setRtLoading(false)
    }
  }

 
  const getThreatLevel = (score: number) => {
    if (score >= 80) return { level: "Critical", color: "bg-red-500" }
    if (score >= 60) return { level: "High", color: "bg-yellow-500" }
    return { level: "Medium", color: "bg-green-500" }
  }

  const getRarityColor = (rarity: string) => {
    switch (rarity) {
      case "Mythical":
        return "from-red-500 to-orange-500"
      case "Legendary":
        return "from-blue-500 to-purple-500"
      case "Rare":
        return "from-green-500 to-blue-500"
      case "Uncommon":
        return "from-yellow-500 to-green-500"
      case "Ultra Rare":
        return "from-blue-600 to-blue-800"
      default:
        return "from-gray-500 to-gray-600"
    }
  }
 
  // Color coding for Press Releases by competitor
  const companyPressBorder = (name: string) => {
    const n = name.toLowerCase()
    if (n.includes("zeiss")) return "border-blue-500"
    if (n.includes("topcon")) return "border-green-500"
    if (n.includes("canon")) return "border-red-500"
    if (n.includes("nidek")) return "border-orange-500"
    if (n.includes("optovue")) return "border-purple-500"
    return "border-blue-500"
  }

  const pressOrder = ["Zeiss","Topcon","Nidek","Canon","Optovue"]
  const pressEntries: { name: string; item?: NewsItem }[] = pressOrder.map((name) => {
    const company = companyData.find((c) => c.name.toLowerCase().includes(name.toLowerCase()))
    const item = company?.news?.[0]
    return { name, item }
  })

  // One patent per competitor (first item), to mirror Press Releases widget
  const patentsEntries: { name: string; item?: PatentLite }[] = pressOrder.map((name) => {
    const list = getPatentsFor(name)
    const item = list?.[0]
    return { name, item }
  })

  // One job per competitor (first item), to mirror Press Releases widget
  const jobsEntries: { name: string; item?: JobItem }[] = pressOrder.map((name) => {
    const comp = companyData.find((c) => c.name.toLowerCase().includes(name.toLowerCase()))
    const item = comp?.Jobs?.[0]
    return { name, item }
  })

  return (
    <div className="min-h-screen bg-background relative">
      {/* Header */}
      <header className="border-b backdrop-blur-sm sticky top-0 z-50" style={{ backgroundColor: "#2E5A87" }}>
        <div className="container mx-auto px-4 py-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <img src="/optos-logo.webp" alt="Optos Logo" className="w-24 h-24 object-contain" />
              <div>
                <h1 className="text-xl font-bold text-white">Eye on Rivals</h1>
                <p className="text-sm text-white/80">Powered by Optos</p>
              </div>
            </div>
            <nav className="hidden md:flex items-center space-x-6">
              <Link href="/" className="text-white hover:text-white/80 transition-colors">
                Dashboard
              </Link>
              <a href="#competitors" className="text-white hover:text-white/80 transition-colors">
                Competitors
              </a>
              <a href="#insights" className="text-white hover:text-white/80 transition-colors">
                Insights
              </a>
              <Link href="/reports" className="text-white hover:text-white/80 transition-colors">
                Reports
              </Link>
            </nav>
            <div className="flex items-center space-x-3">
              <Button
                variant={gamifiedMode ? "default" : "outline"}
                size="sm"
                onClick={() => setGamefiedMode(!gamifiedMode)}
                className="flex items-center gap-2 bg-white text-blue-800 hover:bg-white/90"
              >
                <Gamepad2 className="w-4 h-4" />
                {gamifiedMode ? "Battle Mode" : "Game Mode"}
              </Button>
              <Button variant="outline" size="sm" className="bg-white text-blue-800 border-white hover:bg-white/90">
                Sign In
              </Button>
            </div>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="py-16 bg-gradient-to-br from-background to-muted/50">
        <div className="container mx-auto px-4 text-center">
          <div className="max-w-4xl mx-auto">
            <h2 className="text-4xl md:text-6xl font-bold text-blue-600 mb-6 text-balance">
              Stay Ahead of Your Competition
            </h2>
            <p className="text-xl text-blue-600/80 mb-8 text-pretty">
              Monitor competitors, track market movements, and make data-driven decisions with our gamified competitive
              intelligence platform.
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <Button
                size="lg"
                className="text-lg px-8 bg-blue-500 text-white hover:bg-blue-600"
                onClick={handleStartMonitoring}
                disabled={isScraping}
              >
                <Zap className="w-5 h-5 mr-2" />
                {isScraping ? "Monitoring in Progress..." : "Start Monitoring"}
              </Button>
            </div>
            {scrapeMessage && (
              <div className={`mt-4 p-3 rounded-lg text-center ${
                scrapeMessage.includes("successfully")
                  ? "bg-green-100 text-green-800 border border-green-200"
                  : "bg-red-100 text-red-800 border border-red-200"
              }`}>
                {scrapeMessage}
              </div>
            )}
          </div>
        </div>
      </section>

      {/* Main Dashboard */}
      <section className="py-16">
        <div className="container mx-auto px-4">
          <div className="text-center mb-12">
            <h3 className="text-3xl font-bold text-blue-600 mb-4">
              {gamifiedMode ? "Competitor Battle Arena" : "Interactive Competitor Dashboard"}
            </h3>
            <p className="text-lg text-blue-600/80">
              {gamifiedMode
                ? "Choose your rival and analyze their battle stats"
                : "Real-time intelligence on your key rivals"}
            </p>
          </div>

          {/* Update AI-derived company stats */}
          <div className="flex items-start justify-between gap-4 mb-4">
            <div className="text-left">
              <p className="text-sm text-blue-600/80">
                AI estimates for revenue, products, and patents. Persisted to backend/retinal-stats.json
              </p>
              <div className="text-xs text-blue-600/60">
                {rtUpdatedAt ? `Last updated: ${new Date(rtUpdatedAt).toLocaleString()}` : "No saved stats yet"}
              </div>
              {rtError && <div className="text-xs text-red-600 mt-1">{rtError}</div>}
            </div>
            <div className="text-right">
              <Button
                size="sm"
                onClick={updateRetinalStats}
                disabled={rtLoading}
                className="bg-blue-500 text-white hover:bg-blue-600"
                title="Generate retinal imaging stats with Gemini and persist"
              >
                <RefreshCcw className="w-4 h-4 mr-2" />
                {rtLoading ? "Updating..." : "Update Company Stats"}
              </Button>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-6 mb-12">
            {competitors.map((competitor) => {
              const threat = getThreatLevel(competitor.threatScore)

              if (gamifiedMode) {
                return (
                  <Card
                    key={competitor.id}
                    className={`cursor-pointer transition-all duration-300 hover:scale-105 hover:shadow-2xl border-2 relative overflow-hidden ${
                      selectedCompetitor.id === competitor.id
                        ? "border-blue-500 shadow-2xl ring-2 ring-blue-500/50"
                        : "border-blue-200"
                    }`}
                    onClick={() => setSelectedCompetitor(competitor)}
                  >
                    {/* Pokemon-style gradient background */}
                    <div
                      className={`absolute inset-0 bg-gradient-to-br ${getRarityColor(competitor.rarity)} opacity-10`}
                    />

                    <CardHeader className="pb-2 relative z-10">
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <span className="text-2xl">{competitor.element}</span>
                          <Badge variant="secondary" className={`${competitor.color} text-white text-xs`}>
                            LV.{competitor.level}
                          </Badge>
                        </div>
                        <Badge variant="outline" className="text-xs font-bold text-blue-600/80">
                          {competitor.rarity}
                        </Badge>
                      </div>
                      <CardTitle className="text-lg font-bold text-blue-600">{competitor.name}</CardTitle>
                      <p className="text-xs text-blue-600/80 italic">"{competitor.battleCry}"</p>
                    </CardHeader>

                    <CardContent className="space-y-3 relative z-10">
                      {/* HP Bar */}
                      <div>
                        <div className="flex justify-between text-xs mb-1 text-blue-600/80">
                          <span className="font-semibold text-red-600">HP</span>
                          <span className="font-mono text-blue-600">
                            {competitor.hp}/{competitor.maxHp}
                          </span>
                        </div>
                        <Progress value={(competitor.hp / competitor.maxHp) * 100} className="h-2 bg-red-100" />
                      </div>

                      {/* Battle Stats */}
                      <div className="grid grid-cols-2 gap-2 text-xs">
                        <div className="flex justify-between">
                          <span className="text-blue-600/80">ATK</span>
                          <span className="font-bold text-red-600">{competitor.attack}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-blue-600/80">DEF</span>
                          <span className="font-bold text-blue-600">{competitor.defense}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-blue-600/80">SPD</span>
                          <span className="font-bold text-green-600">{competitor.speed}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-blue-600/80">SPC</span>
                          <span className="font-bold text-purple-600">{competitor.special}</span>
                        </div>
                      </div>

                      {/* Type and Threat */}
                      <div className="flex justify-between items-center">
                        <Badge variant="outline" className="text-xs text-blue-600/80">
                          {competitor.type}
                        </Badge>
                        <Badge className={`${threat.color} text-white text-xs`}>
                          <Flame className="w-3 h-3 mr-1" />
                          {threat.level}
                        </Badge>
                      </div>

                      {/* Market Share as Power Level */}
                      <div>
                        <div className="flex justify-between text-xs mb-1 text-blue-600/80">
                          <span className="font-semibold">Power Level</span>
                          <span className="font-mono text-blue-600">
                            {(msData.find(d => d.name.toLowerCase() === competitor.name.toLowerCase())?.value ?? competitor.marketShare)}%
                          </span>
                        </div>
                        <Progress
                          value={(msData.find(d => d.name.toLowerCase() === competitor.name.toLowerCase())?.value ?? competitor.marketShare)}
                          className="h-1"
                        />
                      </div>
                    </CardContent>
                  </Card>
                )
              }

              // Original card design for non-gamified mode
              return (
                <Card
                  key={competitor.id}
                  className={`cursor-pointer transition-all duration-300 hover:scale-105 hover:shadow-lg border-2 ${
                    selectedCompetitor.id === competitor.id ? "border-blue-500 shadow-lg" : "border-blue-200"
                  }`}
                  onClick={() => setSelectedCompetitor(competitor)}
                >
                  <CardHeader className="pb-3">
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-lg text-blue-600">{competitor.name}</CardTitle>
                      <Badge variant="secondary" className={`${threat.color} text-white`}>
                        {threat.level}
                      </Badge>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div>
                      <div className="flex justify-between text-sm mb-1 text-blue-600/80">
                        <span>Threat Score</span>
                        <span className="font-semibold text-blue-600">{competitor.threatScore}/100</span>
                      </div>
                      <Progress value={competitor.threatScore} className="h-2" />
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-sm">
                      <div>
                        <p className="text-blue-600/80">Market Share</p>
                        <p className="font-semibold text-blue-600">
                          {(msData.find(d => d.name.toLowerCase() === competitor.name.toLowerCase())?.value ?? competitor.marketShare)}%
                        </p>
                      </div>
                      <div>
                        <p className="text-blue-600/80">Products</p>
                        <p className="font-semibold text-blue-600">
                          {rtStats[competitor.name.toLowerCase()]?.products ?? competitor.products}
                        </p>
                      </div>
                      <div>
                        <p className="text-blue-600/80">Patents</p>
                        <p className="font-semibold text-blue-600">
                          {rtStats[competitor.name.toLowerCase()]?.patents ?? competitor.patents}
                        </p>
                      </div>
                      <div>
                        <p className="text-blue-600/80">Revenue</p>
                        <p className="font-semibold text-blue-600">
                          {(rtStats[competitor.name.toLowerCase()]?.revenueUSD ?? 0) > 0
                            ? formatUSDShort(rtStats[competitor.name.toLowerCase()]!.revenueUSD)
                            : competitor.revenue}
                        </p>
                      </div>
                    </div>
                    <Badge variant="outline" className="w-full justify-center text-blue-600/80">
                      <Activity className="w-3 h-3 mr-1" />
                      {competitor.recentActivity} Activity
                    </Badge>
                  </CardContent>
                </Card>
              )
            })}
          </div>

          {gamifiedMode && (
            <div className="mb-12">
              <Card className="border-2 border-blue-600">
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <span className="text-3xl">{selectedCompetitor.element}</span>
                      <div>
                        <CardTitle className="text-2xl text-blue-600">{selectedCompetitor.name}</CardTitle>
                        <p className="text-blue-600/80">
                          {selectedCompetitor.type} • Level {selectedCompetitor.level}
                        </p>
                      </div>
                    </div>
                    <Badge className={`${selectedCompetitor.color} text-white`}>{selectedCompetitor.rarity}</Badge>
                  </div>
                </CardHeader>
                <CardContent className="grid grid-cols-1 md:grid-cols-3 gap-6">
                  {/* Abilities */}
                  <div>
                    <h4 className="font-semibold mb-3 flex items-center gap-2 text-blue-600">
                      <Star className="w-4 h-4" />
                      Special Abilities
                    </h4>
                    <div className="space-y-2">
                      {selectedCompetitor.abilities.map((ability, index) => (
                        <Badge key={index} variant="outline" className="block text-center py-1 text-blue-600/80">
                          {ability}
                        </Badge>
                      ))}
                    </div>
                  </div>

                  {/* Strengths */}
                  <div>
                    <h4 className="font-semibold mb-3 flex items-center gap-2 text-green-600">
                      <Award className="w-4 h-4" />
                      Strengths
                    </h4>
                    <div className="space-y-2">
                      {selectedCompetitor.strengths.map((strength, index) => (
                        <div
                          key={index}
                          className="text-sm p-2 bg-green-50 rounded border-l-2 border-green-500 text-blue-600"
                        >
                          {strength}
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Weaknesses */}
                  <div>
                    <h4 className="font-semibold mb-3 flex items-center gap-2 text-red-600">
                      <Target className="w-4 h-4" />
                      Weaknesses
                    </h4>
                    <div className="space-y-2">
                      {selectedCompetitor.weaknesses.map((weakness, index) => (
                        <div
                          key={index}
                          className="text-sm p-2 bg-red-50 rounded border-l-2 border-red-500 text-blue-600"
                        >
                          {weakness}
                        </div>
                      ))}
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          )}

          {/* Charts Section */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-12">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center text-blue-600">
                  <TrendingUp className="w-5 h-5 mr-2" />
                  Market Trends
                </CardTitle>
                <CardDescription className="text-blue-600/80">
                  Patents, press releases, and job postings over time
                </CardDescription>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={300}>
                  <LineChart data={trendData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#2563eb" />
                    <XAxis dataKey="month" stroke="#2563eb" />
                    <YAxis stroke="#2563eb" />
                    <Tooltip wrapperStyle={{ backgroundColor: "#2E5A87", color: "white" }} />
                    <Line type="monotone" dataKey="patents" stroke="#3b82f6" strokeWidth={2} />
                    <Line type="monotone" dataKey="pressReleases" stroke="#10b981" strokeWidth={2} />
                    <Line type="monotone" dataKey="jobPostings" stroke="#f59e0b" strokeWidth={2} />
                  </LineChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <CardTitle className="flex items-center text-blue-600">
                      <Target className="w-5 h-5 mr-2" />
                      Market Share Distribution
                    </CardTitle>
                    <CardDescription className="text-blue-600/80">
                      Current market positioning
                    </CardDescription>
                    <div className="text-xs mt-1">
                      {msUpdatedAt ? (
                        <span className="text-blue-600/60">Last updated: {new Date(msUpdatedAt).toLocaleString()}</span>
                      ) : (
                        <span className="text-blue-600/60">Using fallback data</span>
                      )}
                      {msError && (
                        <div className="text-red-600 mt-1">{msError}</div>
                      )}
                    </div>
                  </div>
                  <Button
                    size="sm"
                    onClick={updateMarketShare}
                    disabled={msLoading}
                    className="bg-blue-500 text-white hover:bg-blue-600"
                    title="Generate fresh market share with Gemini and persist"
                  >
                    <RefreshCcw className="w-4 h-4 mr-2" />
                    {msLoading ? "Updating..." : "Update"}
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={300}>
                  <PieChart>
                    <Pie
                      data={marketShareData}
                      cx="50%"
                      cy="50%"
                      labelLine={false}
                      label={({ name, value }) => `${name}: ${value}%`}
                      outerRadius={80}
                      fill="#8884d8"
                      dataKey="value"
                    >
                      {marketShareData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color || COLORS[index % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip wrapperStyle={{ backgroundColor: "#2E5A87", color: "white" }} />
                  </PieChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          </div>

          {/* Intelligence Sections */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center text-blue-600">
                  <FileText className="w-5 h-5 mr-2" />
                  Patents
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {patentsEntries.map(({ name, item }) => (
                  <div
                    key={name}
                    className={`border-l-4 pl-4 ${companyPressBorder(name)}`}
                  >
                    <h4 className="font-semibold text-blue-600">
                      {item ? `${name}. ${item.Title}` : `${name}. No patents available.`}
                    </h4>
                    {item && (
                      <>
                        <p className="text-xs text-blue-600/80">{item.Date}</p>
                        <p className="text-xs text-blue-600 break-all">{item.URL}</p>
                      </>
                    )}
                  </div>
                ))}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center text-blue-600">
                  <FileText className="w-5 h-5 mr-2" />
                  Press Releases
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {pressEntries.map(({ name, item }) => (
                  <div
                    key={name}
                    className={`border-l-4 pl-4 ${companyPressBorder(name)}`}
                  >
                    <h4 className="font-semibold text-blue-600">
                      {item ? `${name}. ${item.Headline}` : `${name}. No press releases available.`}
                    </h4>
                    {item && (
                      <>
                        <p className="text-xs text-blue-600/80">{item.Date}</p>
                        <a
                          href={item.URL}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-sm text-blue-600 underline"
                        >
                          View press release
                        </a>
                      </>
                    )}
                  </div>
                ))}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center text-blue-600">
                  <Users className="w-5 h-5 mr-2" />
                  Job Postings
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {jobsEntries.map(({ name, item }) => (
                  <div
                    key={name}
                    className={`border-l-4 pl-4 ${companyPressBorder(name)}`}
                  >
                    <h4 className="font-semibold text-blue-600">
                      {item ? `${name}. ${item["Job Title"]}` : `${name}. No job postings available.`}
                    </h4>
                    {item && (
                      <>
                        <p className="text-xs text-blue-600/80">{item.Date}</p>
                        <a
                          href={item.URL}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-sm text-blue-600 underline"
                        >
                          View job posting
                        </a>
                      </>
                    )}
                  </div>
                ))}
              </CardContent>
            </Card>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-2" style={{ backgroundColor: "#2E5A87" }}>
        <div className="container mx-auto px-2">
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
      
      {/* Video overlay */}
      {showVideo && (
        <div className="fixed inset-0 backdrop-blur-sm z-50 flex items-center justify-center">
          <div className="relative">
            <video
              autoPlay
              loop
              muted
              playsInline
              className="w-96 h-96 rounded-lg shadow-2xl"
            >
              <source src="/theEye.mp4" type="video/mp4" />
              Your browser does not support the video tag.
            </video>
          </div>
        </div>
      )}
    </div>
  )
}
