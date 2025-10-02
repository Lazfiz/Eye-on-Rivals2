"use client"

import { useState } from "react"
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
} from "lucide-react"

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
    name: "Heidelberg Engineering",
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

// Mock trend data
const trendData = [
  { month: "Jan", patents: 12, products: 3, jobPostings: 45 },
  { month: "Feb", patents: 15, products: 2, jobPostings: 52 },
  { month: "Mar", patents: 18, products: 4, jobPostings: 38 },
  { month: "Apr", patents: 22, products: 1, jobPostings: 61 },
  { month: "May", patents: 19, products: 3, jobPostings: 47 },
  { month: "Jun", patents: 25, products: 5, jobPostings: 73 },
]

const marketShareData = [
  { name: "Optos", value: 40, color: "#2563eb" },
  ...competitors.map((comp) => ({
    name: comp.name,
    value: comp.marketShare,
    color: comp.color.replace("bg-", "#"),
  })),
]

const COLORS = ["#2563eb", "#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6"]

export default function EyeOnRivalsLanding() {
  const [selectedCompetitor, setSelectedCompetitor] = useState(competitors[0])
  const [gamifiedMode, setGamefiedMode] = useState(false)

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

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b backdrop-blur-sm sticky top-0 z-50" style={{ backgroundColor: "#2E5A87" }}>
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <img src="/optos-logo.webp" alt="Optos Logo" className="w-64 h-64 object-contain" />
              <div>
                <h1 className="text-xl font-bold text-white">Eye on Rivals</h1>
                <p className="text-sm text-white/80">Powered by Optos</p>
              </div>
            </div>
            <nav className="hidden md:flex items-center space-x-6">
              <a href="#dashboard" className="text-white hover:text-white/80 transition-colors">
                Dashboard
              </a>
              <a href="#competitors" className="text-white hover:text-white/80 transition-colors">
                Competitors
              </a>
              <a href="#insights" className="text-white hover:text-white/80 transition-colors">
                Insights
              </a>
              <a href="#reports" className="text-white hover:text-white/80 transition-colors">
                Reports
              </a>
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
              Stay Ahead of Your <span className="text-blue-500">Competition</span>
            </h2>
            <p className="text-xl text-blue-600/80 mb-8 text-pretty">
              Monitor competitors, track market movements, and make data-driven decisions with our gamified competitive
              intelligence platform.
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <Button size="lg" className="text-lg px-8 bg-blue-500 text-white hover:bg-blue-600">
                <Zap className="w-5 h-5 mr-2" />
                Start Monitoring
              </Button>
            </div>
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
                          <span className="font-mono text-blue-600">{competitor.marketShare}%</span>
                        </div>
                        <Progress value={competitor.marketShare} className="h-1" />
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
                        <p className="font-semibold text-blue-600">{competitor.marketShare}%</p>
                      </div>
                      <div>
                        <p className="text-blue-600/80">Products</p>
                        <p className="font-semibold text-blue-600">{competitor.products}</p>
                      </div>
                      <div>
                        <p className="text-blue-600/80">Patents</p>
                        <p className="font-semibold text-blue-600">{competitor.patents}</p>
                      </div>
                      <div>
                        <p className="text-blue-600/80">Revenue</p>
                        <p className="font-semibold text-blue-600">{competitor.revenue}</p>
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
                  Patents, products, and job postings over time
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
                    <Line type="monotone" dataKey="products" stroke="#10b981" strokeWidth={2} />
                    <Line type="monotone" dataKey="jobPostings" stroke="#f59e0b" strokeWidth={2} />
                  </LineChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center text-blue-600">
                  <Target className="w-5 h-5 mr-2" />
                  Market Share Distribution
                </CardTitle>
                <CardDescription className="text-blue-600/80">Current market positioning</CardDescription>
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
                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
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
                  <Briefcase className="w-5 h-5 mr-2" />
                  Product Updates
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="border-l-4 border-blue-500 pl-4">
                  <h4 className="font-semibold text-blue-600">Zeiss OCT Update</h4>
                  <p className="text-sm text-blue-600/80">New AI-powered analysis features</p>
                  <p className="text-xs text-blue-600/80">2 days ago</p>
                </div>
                <div className="border-l-4 border-green-500 pl-4">
                  <h4 className="font-semibold text-blue-600">Canon Fundus Camera</h4>
                  <p className="text-sm text-blue-600/80">Enhanced imaging capabilities</p>
                  <p className="text-xs text-blue-600/80">1 week ago</p>
                </div>
                <div className="border-l-4 border-yellow-500 pl-4">
                  <h4 className="font-semibold text-blue-600">Topcon Software Suite</h4>
                  <p className="text-sm text-blue-600/80">Cloud integration announced</p>
                  <p className="text-xs text-blue-600/80">2 weeks ago</p>
                </div>
                <div className="border-l-4 border-purple-500 pl-4">
                  <h4 className="font-semibold text-blue-600">Heidelberg Expansion</h4>
                  <p className="text-sm text-blue-600/80">New facility in Asia announced</p>
                  <p className="text-xs text-blue-600/80">2 weeks ago</p>
                </div>
                <div className="border-l-4 border-yellow-500 pl-4">
                  <h4 className="font-semibold text-blue-600">Nidek Rapid Development</h4>
                  <p className="text-sm text-blue-600/80">New product development initiatives</p>
                  <p className="text-xs text-blue-600/80">3 weeks ago</p>
                </div>
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
                <div className="border-l-4 border-red-500 pl-4">
                  <h4 className="font-semibold text-blue-600">Canon Q3 Results</h4>
                  <p className="text-sm text-blue-600/80">Strong growth in medical imaging</p>
                  <p className="text-xs text-blue-600/80">3 days ago</p>
                </div>
                <div className="border-l-4 border-blue-500 pl-4">
                  <h4 className="font-semibold text-blue-600">Zeiss Partnership</h4>
                  <p className="text-sm text-blue-600/80">Strategic alliance with tech startup</p>
                  <p className="text-xs text-blue-600/80">1 week ago</p>
                </div>
                <div className="border-l-4 border-green-500 pl-4">
                  <h4 className="font-semibold text-blue-600">Topcon Cloud Integration</h4>
                  <p className="text-sm text-blue-600/80">Topcon announces cloud integration</p>
                  <p className="text-xs text-blue-600/80">2 weeks ago</p>
                </div>
                <div className="border-l-4 border-yellow-500 pl-4">
                  <h4 className="font-semibold text-blue-600">Nidek Tech Evolution</h4>
                  <p className="text-sm text-blue-600/80">Nidek focuses on tech evolution</p>
                  <p className="text-xs text-blue-600/80">3 weeks ago</p>
                </div>
                <div className="border-l-4 border-purple-500 pl-4">
                  <h4 className="font-semibold text-blue-600">Heidelberg Expansion</h4>
                  <p className="text-sm text-blue-600/80">New facility in Asia announced</p>
                  <p className="text-xs text-blue-600/80">2 weeks ago</p>
                </div>
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
                <div className="border-l-4 border-green-500 pl-4">
                  <h4 className="font-semibold text-blue-600">Senior AI Engineer</h4>
                  <p className="text-sm text-blue-600/80">Zeiss - Medical Imaging Division</p>
                  <p className="text-xs text-blue-600/80">Posted today</p>
                </div>
                <div className="border-l-4 border-blue-500 pl-4">
                  <h4 className="font-semibold text-blue-600">Product Manager</h4>
                  <p className="text-sm text-blue-600/80">Canon - Healthcare Solutions</p>
                  <p className="text-xs text-blue-600/80">2 days ago</p>
                </div>
                <div className="border-l-4 border-yellow-500 pl-4">
                  <h4 className="font-semibold text-blue-600">R&D Director</h4>
                  <p className="text-sm text-blue-600/80">Topcon - Innovation Lab</p>
                  <p className="text-xs text-blue-600/80">5 days ago</p>
                </div>
                <div className="border-l-4 border-purple-500 pl-4">
                  <h4 className="font-semibold text-blue-600">Market Analyst</h4>
                  <p className="text-sm text-blue-600/80">Heidelberg Engineering - Market Analysis Team</p>
                  <p className="text-xs text-blue-600/80">2 weeks ago</p>
                </div>
                <div className="border-l-4 border-yellow-500 pl-4">
                  <h4 className="font-semibold text-blue-600">Technical Support Engineer</h4>
                  <p className="text-sm text-blue-600/80">Nidek - Technical Support</p>
                  <p className="text-xs text-blue-600/80">3 weeks ago</p>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-12" style={{ backgroundColor: "#2E5A87" }}>
        <div className="container mx-auto px-4">
          <div className="flex flex-col md:flex-row justify-between items-center">
            <div className="flex items-center space-x-3 mb-4 md:mb-0">
              <img src="/optos-logo.webp" alt="Optos Logo" className="w-40 h-40 object-contain" />
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
            <p>&copy; 2024 Eye on Rivals. Powered by Optos. All rights reserved.</p>
          </div>
        </div>
      </footer>
    </div>
  )
}
