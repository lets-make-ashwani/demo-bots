"use client";

import { useEffect, useState, useMemo } from "react";
import { 
  Users, 
  MessageSquareCode, 
  Cpu, 
  Clock, 
  Activity, 
  Search, 
  RefreshCw, 
  LogOut, 
  MessageCircle,
  Hash,
  Sparkles,
  Calendar,
  Layers,
  ArrowRightLeft,
  ChevronRight,
  TrendingUp,
  Database
} from "lucide-react";

interface UserStats {
  totalUsers: number;
  activeUsers24h: number;
  totalMessages: number;
  totalTokens: number;
  totalPromptTokens: number;
  totalCompletionTokens: number;
  avgResponseTime: number;
}

interface ModelBreakdown {
  model: string;
  count: number;
}

interface DailyVolume {
  date: string;
  messageCount: number;
  tokenCount: number;
}

interface User {
  telegram_id: number;
  username?: string;
  first_name: string;
  last_name?: string;
  language: string;
  total_messages: number;
  total_tokens: number;
  created_at: string;
  updated_at: string;
  last_seen: string;
}

interface Conversation {
  _id: string;
  user_id: number;
  title: string;
  model: string;
  summary?: string;
  created_at: string;
  updated_at: string;
}

interface Message {
  _id: string;
  conversation_id: string;
  user_id: number;
  role: "user" | "assistant";
  content: string;
  model?: string;
  prompt_tokens?: number;
  completion_tokens?: number;
  total_tokens?: number;
  response_time?: number;
  created_at: string;
}

export default function Dashboard() {
  // Page States
  const [stats, setStats] = useState<UserStats | null>(null);
  const [modelBreakdown, setModelBreakdown] = useState<ModelBreakdown[]>([]);
  const [dailyVolume, setDailyVolume] = useState<DailyVolume[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  
  // Selection and search states
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [selectedConversation, setSelectedConversation] = useState<Conversation | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  
  // Loading states
  const [isStatsLoading, setIsStatsLoading] = useState(true);
  const [isUsersLoading, setIsUsersLoading] = useState(true);
  const [isConvsLoading, setIsConvsLoading] = useState(false);
  const [isMsgsLoading, setIsMsgsLoading] = useState(false);
  
  // Refresh trackers
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  // Logout/clear session passcode
  const handleLogout = async () => {
    // Simply clear the cookie by setting it to expire
    document.cookie = "dashboard_passcode=; path=/; expires=Thu, 01 Jan 1970 00:00:00 UTC;";
    window.location.reload();
  };

  // Fetch Stats & Users on mount / refresh trigger
  useEffect(() => {
    async function loadStats() {
      setIsStatsLoading(true);
      try {
        const res = await fetch("/api/stats");
        if (res.ok) {
          const data = await res.json();
          setStats(data.stats);
          setModelBreakdown(data.modelBreakdown);
          setDailyVolume(data.dailyVolume);
        }
      } catch (err) {
        console.error("Error loading stats:", err);
      } finally {
        setIsStatsLoading(false);
      }
    }

    async function loadUsers() {
      setIsUsersLoading(true);
      try {
        const res = await fetch(`/api/users?search=${encodeURIComponent(searchQuery)}`);
        if (res.ok) {
          const data = await res.json();
          setUsers(data.users || []);
        }
      } catch (err) {
        console.error("Error loading users:", err);
      } finally {
        setIsUsersLoading(false);
      }
    }

    loadStats();
    loadUsers();
  }, [refreshTrigger, searchQuery]);

  // Load conversations when selected user changes
  useEffect(() => {
    const targetUser = selectedUser;
    if (!targetUser) {
      setConversations([]);
      setSelectedConversation(null);
      return;
    }

    async function loadConversations(user: User) {
      setIsConvsLoading(true);
      setSelectedConversation(null);
      setMessages([]);
      try {
        const res = await fetch(`/api/users/${user.telegram_id}/conversations`);
        if (res.ok) {
          const data = await res.json();
          setConversations(data.conversations || []);
          
          // Auto-select first conversation if available
          if (data.conversations && data.conversations.length > 0) {
            setSelectedConversation(data.conversations[0]);
          }
        }
      } catch (err) {
        console.error("Error loading conversations:", err);
      } finally {
        setIsConvsLoading(false);
      }
    }

    loadConversations(targetUser);
  }, [selectedUser]);

  // Load messages when selected conversation changes
  useEffect(() => {
    const targetConv = selectedConversation;
    if (!targetConv) {
      setMessages([]);
      return;
    }

    async function loadMessages(conv: Conversation) {
      setIsMsgsLoading(true);
      try {
        const res = await fetch(`/api/conversations/${conv._id}/messages`);
        if (res.ok) {
          const data = await res.json();
          setMessages(data.messages || []);
        }
      } catch (err) {
        console.error("Error loading messages:", err);
      } finally {
        setIsMsgsLoading(false);
      }
    }

    loadMessages(targetConv);
  }, [selectedConversation]);

  // Formatting helpers
  const formatTokens = (tokens: number) => {
    if (tokens >= 1_000_000) return `${(tokens / 1_000_000).toFixed(1)}M`;
    if (tokens >= 1_000) return `${(tokens / 1_000).toFixed(1)}k`;
    return tokens.toString();
  };

  const formatDate = (dateStr?: string) => {
    if (!dateStr) return "N/A";
    const date = new Date(dateStr);
    return date.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit"
    });
  };

  const formatLastSeen = (dateStr?: string) => {
    if (!dateStr) return "Never";
    const date = new Date(dateStr);
    const diffMs = Date.now() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);

    if (diffMins < 1) return "Just now";
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  };

  // SVG Chart Config and Drawing
  const chartWidth = 500;
  const chartHeight = 120;
  const padding = 15;

  const chartPaths = useMemo(() => {
    if (dailyVolume.length === 0) return { messagePath: "", tokenPath: "", points: [] };

    const maxMsgs = Math.max(...dailyVolume.map(d => d.messageCount), 1);
    const maxTokens = Math.max(...dailyVolume.map(d => d.tokenCount), 1);

    const stepX = (chartWidth - padding * 2) / (dailyVolume.length - 1 || 1);
    
    // Draw message count chart path
    let messagePoints = dailyVolume.map((d, index) => {
      const x = padding + index * stepX;
      const y = chartHeight - padding - ((d.messageCount / maxMsgs) * (chartHeight - padding * 2));
      return { x, y, val: d.messageCount, date: d.date };
    });

    // Draw token count chart path
    let tokenPoints = dailyVolume.map((d, index) => {
      const x = padding + index * stepX;
      const y = chartHeight - padding - ((d.tokenCount / maxTokens) * (chartHeight - padding * 2));
      return { x, y, val: d.tokenCount, date: d.date };
    });

    const createPath = (points: { x: number; y: number }[]) => {
      if (points.length === 0) return "";
      let p = `M ${points[0].x} ${points[0].y}`;
      for (let i = 1; i < points.length; i++) {
        // Curve to point
        const cpX1 = points[i-1].x + stepX / 3;
        const cpY1 = points[i-1].y;
        const cpX2 = points[i].x - stepX / 3;
        const cpY2 = points[i].y;
        p += ` C ${cpX1} ${cpY1}, ${cpX2} ${cpY2}, ${points[i].x} ${points[i].y}`;
      }
      return p;
    };

    const createAreaPath = (points: { x: number; y: number }[]) => {
      const linePath = createPath(points);
      if (!linePath) return "";
      return `${linePath} L ${points[points.length-1].x} ${chartHeight - padding} L ${points[0].x} ${chartHeight - padding} Z`;
    };

    return {
      messageLine: createPath(messagePoints),
      messageArea: createAreaPath(messagePoints),
      tokenLine: createPath(tokenPoints),
      tokenArea: createAreaPath(tokenPoints),
      messagePoints,
      tokenPoints
    };
  }, [dailyVolume]);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans antialiased selection:bg-violet-500/30">
      {/* Decorative Background Elements */}
      <div className="absolute top-0 right-1/4 h-[500px] w-[500px] rounded-full bg-violet-600/10 blur-[120px] pointer-events-none" />
      <div className="absolute bottom-10 left-1/4 h-[500px] w-[500px] rounded-full bg-indigo-600/10 blur-[120px] pointer-events-none" />

      {/* Main Container */}
      <div className="relative z-10 mx-auto max-w-[1600px] px-4 py-6 sm:px-6 lg:px-8">
        
        {/* Header Block */}
        <header className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between border-b border-slate-900 pb-6 mb-8">
          <div className="flex items-center gap-3">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-tr from-violet-600 to-indigo-600 text-white shadow-lg shadow-violet-500/10">
              <Activity className="h-6 w-6" />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
                AI Assistant Monitoring Panel
                <span className="inline-flex items-center rounded-full bg-violet-500/10 px-2 py-1 text-xs font-medium text-violet-400 ring-1 ring-inset ring-violet-500/20">
                  Live
                </span>
              </h1>
              <p className="text-sm text-slate-400">Track server health, user activity, tokens, and real-time chat histories</p>
            </div>
          </div>
          
          <div className="flex items-center gap-3">
            <button
              onClick={() => setRefreshTrigger(prev => prev + 1)}
              className="inline-flex items-center gap-2 rounded-xl bg-slate-900 border border-slate-800 hover:bg-slate-800 hover:border-slate-700 active:scale-[0.98] transition-all px-4 py-2.5 text-sm font-semibold text-slate-200"
            >
              <RefreshCw className={`h-4 w-4 ${isStatsLoading ? "animate-spin" : ""}`} />
              Refresh Data
            </button>
            <button
              onClick={handleLogout}
              className="inline-flex items-center gap-2 rounded-xl bg-red-950/20 border border-red-900/30 hover:bg-red-950/40 active:scale-[0.98] transition-all px-4 py-2.5 text-sm font-semibold text-red-400"
            >
              <LogOut className="h-4 w-4" />
              Lock Panel
            </button>
          </div>
        </header>

        {/* Stats Grid */}
        <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5 mb-8">
          {[
            {
              title: "Total Registered Users",
              value: stats ? stats.totalUsers : 0,
              icon: Users,
              color: "from-violet-500 to-purple-500",
              desc: `${stats ? stats.activeUsers24h : 0} active in last 24h`
            },
            {
              title: "Total Dialogues Logged",
              value: stats ? stats.totalMessages : 0,
              icon: MessageSquareCode,
              color: "from-blue-500 to-indigo-500",
              desc: "User & assistant replies"
            },
            {
              title: "Token Usage (Total)",
              value: stats ? formatTokens(stats.totalTokens) : "0",
              icon: Cpu,
              color: "from-emerald-500 to-teal-500",
              desc: stats ? `Prompt: ${formatTokens(stats.totalPromptTokens)} | Comp: ${formatTokens(stats.totalCompletionTokens)}` : ""
            },
            {
              title: "Average Latency",
              value: stats ? `${stats.avgResponseTime}s` : "0s",
              icon: Clock,
              color: "from-amber-500 to-orange-500",
              desc: "Bot response generation time"
            },
            {
              title: "Active Models",
              value: modelBreakdown.length,
              icon: Sparkles,
              color: "from-pink-500 to-rose-500",
              desc: modelBreakdown[0] ? `Top: ${modelBreakdown[0].model.split("/").pop()}` : "No model usage recorded"
            }
          ].map((item, index) => {
            const Icon = item.icon;
            return (
              <div
                key={index}
                className="relative overflow-hidden rounded-2xl border border-slate-900 bg-slate-900/40 p-6 backdrop-blur-md shadow-lg group hover:border-slate-800 transition-all duration-300"
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-slate-400">{item.title}</span>
                  <div className={`flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-tr ${item.color} text-white shadow-md group-hover:scale-105 transition-transform duration-300`}>
                    <Icon className="h-5 w-5" />
                  </div>
                </div>
                {isStatsLoading ? (
                  <div className="mt-4 h-8 w-24 rounded bg-slate-800 animate-pulse" />
                ) : (
                  <div className="mt-4">
                    <span className="text-2xl font-bold tracking-tight text-white">{item.value}</span>
                    <p className="mt-1 text-xs text-slate-500 truncate">{item.desc}</p>
                  </div>
                )}
              </div>
            );
          })}
        </section>

        {/* Charts & Analytics Visualizer */}
        <section className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
          {/* Daily Activity Chart */}
          <div className="lg:col-span-2 rounded-2xl border border-slate-900 bg-slate-900/30 p-6 backdrop-blur-md">
            <div className="flex items-center justify-between mb-6">
              <div>
                <h3 className="text-lg font-bold text-white flex items-center gap-2">
                  <TrendingUp className="h-5 w-5 text-indigo-400" />
                  System Activity & Volume (Last 7 Days)
                </h3>
                <p className="text-xs text-slate-400">Interactive timeline of chat counts and tokens</p>
              </div>
              <div className="flex items-center gap-4 text-xs font-semibold">
                <span className="flex items-center gap-1.5 text-violet-400">
                  <span className="h-2.5 w-2.5 rounded-full bg-violet-500" />
                  Messages
                </span>
                <span className="flex items-center gap-1.5 text-indigo-400">
                  <span className="h-2.5 w-2.5 rounded-full bg-indigo-500" />
                  Tokens
                </span>
              </div>
            </div>

            {isStatsLoading ? (
              <div className="h-[120px] w-full rounded bg-slate-900/60 animate-pulse flex items-center justify-center text-slate-500 text-sm">
                Drawing metrics...
              </div>
            ) : dailyVolume.length === 0 ? (
              <div className="h-[120px] w-full border border-dashed border-slate-800 rounded-xl flex items-center justify-center text-slate-500 text-sm">
                No activity data available
              </div>
            ) : (
              <div className="w-full overflow-hidden">
                {/* SVG Graph */}
                <svg viewBox={`0 0 ${chartWidth} ${chartHeight}`} className="w-full h-36">
                  <defs>
                    <linearGradient id="msgGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#8b5cf6" stopOpacity="0.25"/>
                      <stop offset="100%" stopColor="#8b5cf6" stopOpacity="0"/>
                    </linearGradient>
                    <linearGradient id="tokenGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#6366f1" stopOpacity="0.25"/>
                      <stop offset="100%" stopColor="#6366f1" stopOpacity="0"/>
                    </linearGradient>
                  </defs>

                  {/* Grid Lines */}
                  <line x1={padding} y1={padding} x2={chartWidth - padding} y2={padding} stroke="#1e293b" strokeDasharray="3 3"/>
                  <line x1={padding} y1={chartHeight / 2} x2={chartWidth - padding} y2={chartHeight / 2} stroke="#1e293b" strokeDasharray="3 3"/>
                  <line x1={padding} y1={chartHeight - padding} x2={chartWidth - padding} y2={chartHeight - padding} stroke="#1e293b"/>

                  {/* Areas */}
                  <path d={chartPaths.messageArea} fill="url(#msgGrad)"/>
                  <path d={chartPaths.tokenArea} fill="url(#tokenGrad)"/>

                  {/* Lines */}
                  <path d={chartPaths.messageLine} fill="none" stroke="#8b5cf6" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                  <path d={chartPaths.tokenLine} fill="none" stroke="#6366f1" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>

                  {/* Message Dots & Tooltips */}
                  {chartPaths.messagePoints?.map((pt, i) => (
                    <g key={`msg-${i}`} className="group/dot cursor-pointer">
                      <circle cx={pt.x} cy={pt.y} r="3" fill="#8b5cf6" className="hover:r-5 transition-all"/>
                      <title>{`Date: ${pt.date}\nMessages: ${pt.val}`}</title>
                    </g>
                  ))}
                  
                  {/* Token Dots */}
                  {chartPaths.tokenPoints?.map((pt, i) => (
                    <g key={`token-${i}`} className="group/dot cursor-pointer">
                      <circle cx={pt.x} cy={pt.y} r="3" fill="#6366f1" className="hover:r-5 transition-all"/>
                      <title>{`Date: ${pt.date}\nTokens: ${formatTokens(pt.val)}`}</title>
                    </g>
                  ))}
                </svg>

                {/* X-axis Labels */}
                <div className="flex justify-between px-2 text-[10px] text-slate-500 font-mono mt-1">
                  {dailyVolume.map((d, index) => {
                    const date = new Date(d.date);
                    return <span key={index}>{date.toLocaleDateString("en-US", { month: "short", day: "numeric" })}</span>;
                  })}
                </div>
              </div>
            )}
          </div>

          {/* Model distribution */}
          <div className="rounded-2xl border border-slate-900 bg-slate-900/30 p-6 backdrop-blur-md">
            <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
              <Layers className="h-5 w-5 text-pink-400" />
              LLM Model Distribution
            </h3>
            {isStatsLoading ? (
              <div className="space-y-3">
                <div className="h-8 rounded bg-slate-800 animate-pulse" />
                <div className="h-8 rounded bg-slate-800 animate-pulse" />
                <div className="h-8 rounded bg-slate-800 animate-pulse" />
              </div>
            ) : modelBreakdown.length === 0 ? (
              <div className="h-32 border border-dashed border-slate-800 rounded-xl flex items-center justify-center text-slate-500 text-sm">
                No model details recorded
              </div>
            ) : (
              <div className="space-y-4">
                {modelBreakdown.map((item, index) => {
                  // Get model shorthand name
                  const shortName = item.model.split("/").pop() || item.model;
                  const total = modelBreakdown.reduce((sum, current) => sum + current.count, 0);
                  const percent = total > 0 ? ((item.count / total) * 100).toFixed(0) : "0";

                  // Alternate progress bar colors
                  const colors = ["bg-violet-500", "bg-indigo-500", "bg-pink-500", "bg-teal-500"];
                  const color = colors[index % colors.length];

                  return (
                    <div key={index} className="space-y-1">
                      <div className="flex items-center justify-between text-xs">
                        <span className="font-semibold text-slate-300 truncate max-w-[200px]" title={item.model}>
                          {shortName}
                        </span>
                        <span className="font-mono text-slate-400">{item.count} ({percent}%)</span>
                      </div>
                      <div className="h-2 w-full bg-slate-950 rounded-full overflow-hidden">
                        <div 
                          className={`h-full rounded-full ${color}`} 
                          style={{ width: `${percent}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </section>

        {/* Real-time Monitoring & Dialogue Console */}
        <section className="grid grid-cols-1 xl:grid-cols-12 gap-6 items-stretch">
          
          {/* Left panel: User List (width 4 columns) */}
          <div className="xl:col-span-4 rounded-2xl border border-slate-900 bg-slate-900/20 backdrop-blur-md flex flex-col h-[650px] overflow-hidden">
            {/* User header with search */}
            <div className="p-4 border-b border-slate-900 space-y-3 bg-slate-900/40">
              <h3 className="text-md font-bold text-white flex items-center gap-2">
                <Users className="h-4.5 w-4.5 text-violet-400" />
                Chat Users ({users.length})
              </h3>
              <div className="relative">
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search by username, ID or name..."
                  className="w-full text-xs rounded-xl border border-slate-800 bg-slate-950/80 py-2.5 pl-9 pr-4 text-slate-100 placeholder:text-slate-600 focus:border-violet-500 focus:outline-none transition duration-200"
                />
                <div className="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none">
                  <Search className="h-4 w-4 text-slate-600" />
                </div>
              </div>
            </div>

            {/* Users list container */}
            <div className="flex-1 overflow-y-auto p-2 space-y-1">
              {isUsersLoading ? (
                Array.from({ length: 6 }).map((_, i) => (
                  <div key={i} className="h-16 rounded-xl bg-slate-900/40 animate-pulse p-3 flex gap-3">
                    <div className="h-10 w-10 rounded-full bg-slate-800" />
                    <div className="space-y-2 flex-1">
                      <div className="h-3 w-20 rounded bg-slate-800" />
                      <div className="h-2 w-32 rounded bg-slate-800" />
                    </div>
                  </div>
                ))
              ) : users.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center text-slate-500 text-xs py-10 space-y-2">
                  <Database className="h-8 w-8 text-slate-700" />
                  <span>No chat users found</span>
                </div>
              ) : (
                users.map((user) => {
                  const isSelected = selectedUser?.telegram_id === user.telegram_id;
                  const initials = user.first_name ? user.first_name.charAt(0) : "?";
                  
                  return (
                    <button
                      key={user.telegram_id}
                      onClick={() => setSelectedUser(user)}
                      className={`w-full text-left p-3 rounded-xl flex items-center justify-between transition-all group ${
                        isSelected 
                          ? "bg-gradient-to-r from-violet-600/20 to-indigo-600/10 border border-violet-500/20 text-white" 
                          : "border border-transparent hover:bg-slate-900/60 text-slate-300"
                      }`}
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        {/* Profile placeholder */}
                        <div className={`h-9 w-9 rounded-xl flex items-center justify-center font-bold text-xs shrink-0 select-none ${
                          isSelected 
                            ? "bg-violet-600 text-white shadow-lg shadow-violet-500/20" 
                            : "bg-slate-900 border border-slate-800 text-slate-400 group-hover:border-slate-700 group-hover:text-slate-200 transition-colors"
                        }`}>
                          {initials}
                        </div>
                        <div className="min-w-0">
                          <div className="flex items-center gap-1.5">
                            <span className="font-semibold text-xs truncate max-w-[120px]">
                              {user.first_name} {user.last_name || ""}
                            </span>
                            {user.username && (
                              <span className="text-[10px] text-slate-500 truncate max-w-[80px]">
                                @{user.username}
                              </span>
                            )}
                          </div>
                          <span className="block text-[10px] text-slate-500 font-mono mt-0.5 truncate">
                            ID: {user.telegram_id} • Msg: {user.total_messages}
                          </span>
                        </div>
                      </div>
                      <div className="text-right shrink-0">
                        <span className="block text-[10px] font-medium text-slate-500">
                          {formatLastSeen(user.last_seen)}
                        </span>
                        <span className="inline-block text-[9px] font-mono font-semibold bg-slate-950/80 border border-slate-900 text-indigo-400 rounded px-1.5 py-0.5 mt-0.5">
                          {formatTokens(user.total_tokens)} tkn
                        </span>
                      </div>
                    </button>
                  );
                })
              )}
            </div>
          </div>

          {/* Middle panel: Conversations (width 3 columns) */}
          <div className="xl:col-span-3 rounded-2xl border border-slate-900 bg-slate-900/20 backdrop-blur-md flex flex-col h-[650px] overflow-hidden">
            <div className="p-4 border-b border-slate-900 bg-slate-900/40">
              <h3 className="text-md font-bold text-white flex items-center gap-2">
                <MessageCircle className="h-4.5 w-4.5 text-indigo-400" />
                Sessions ({conversations.length})
              </h3>
              <p className="text-[10px] text-slate-500">Conversation sessions for selected user</p>
            </div>

            <div className="flex-1 overflow-y-auto p-2 space-y-1">
              {!selectedUser ? (
                <div className="h-full flex flex-col items-center justify-center text-slate-500 text-xs py-10 text-center px-4 space-y-2">
                  <Users className="h-8 w-8 text-slate-700 animate-bounce" />
                  <span>Select a user to monitor their sessions</span>
                </div>
              ) : isConvsLoading ? (
                Array.from({ length: 4 }).map((_, i) => (
                  <div key={i} className="h-20 rounded-xl bg-slate-900/40 animate-pulse p-3 space-y-2">
                    <div className="h-3.5 w-24 rounded bg-slate-800" />
                    <div className="h-3 w-40 rounded bg-slate-800" />
                  </div>
                ))
              ) : conversations.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center text-slate-500 text-xs py-10 space-y-1">
                  <span>No sessions found</span>
                </div>
              ) : (
                conversations.map((conv) => {
                  const isSelected = selectedConversation?._id === conv._id;
                  const modelShort = conv.model.split("/").pop() || conv.model;
                  
                  return (
                    <button
                      key={conv._id}
                      onClick={() => setSelectedConversation(conv)}
                      className={`w-full text-left p-3 rounded-xl border transition-all flex flex-col gap-1.5 ${
                        isSelected 
                          ? "bg-slate-900 border-indigo-500/20 shadow-md text-white" 
                          : "border-transparent hover:bg-slate-900/40 text-slate-300"
                      }`}
                    >
                      <div className="flex items-start justify-between gap-1 w-full">
                        <span className="font-semibold text-xs line-clamp-1 flex-1">
                          {conv.title || "Untitled Session"}
                        </span>
                        <ChevronRight className={`h-4 w-4 shrink-0 transition-transform ${isSelected ? "text-indigo-400 rotate-90" : "text-slate-600"}`} />
                      </div>
                      
                      {conv.summary && (
                        <p className="text-[10px] text-slate-500 line-clamp-2 italic leading-relaxed">
                          "{conv.summary}"
                        </p>
                      )}

                      <div className="flex items-center justify-between text-[9px] text-slate-400 font-mono mt-1 border-t border-slate-900/60 pt-1.5">
                        <span className="truncate max-w-[110px] bg-slate-950 px-1 py-0.5 rounded text-violet-400 font-semibold" title={conv.model}>
                          {modelShort}
                        </span>
                        <span>{formatDate(conv.updated_at)}</span>
                      </div>
                    </button>
                  );
                })
              )}
            </div>
          </div>

          {/* Right panel: Chat Viewer (width 5 columns) */}
          <div className="xl:col-span-5 rounded-2xl border border-slate-900 bg-slate-900/20 backdrop-blur-md flex flex-col h-[650px] overflow-hidden">
            {/* Header details */}
            <div className="p-4 border-b border-slate-900 bg-slate-900/40 flex items-center justify-between shrink-0">
              <div>
                <h3 className="text-md font-bold text-white flex items-center gap-2">
                  <Hash className="h-4.5 w-4.5 text-pink-400" />
                  Dialogue Thread
                </h3>
                {selectedConversation ? (
                  <p className="text-[10px] text-slate-400 truncate max-w-[300px]">
                    Session ID: <span className="font-mono text-slate-500">{selectedConversation._id}</span>
                  </p>
                ) : (
                  <p className="text-[10px] text-slate-500">Live chat dialogue</p>
                )}
              </div>
              
              {selectedConversation && (
                <div className="flex items-center gap-1.5 text-[9px] font-mono bg-indigo-500/10 text-indigo-400 rounded-lg px-2.5 py-1 ring-1 ring-inset ring-indigo-500/20">
                  <Sparkles className="h-3 w-3 shrink-0" />
                  <span>{selectedConversation.model.split("/").pop()}</span>
                </div>
              )}
            </div>

            {/* Message list bubble log */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-slate-950/40">
              {!selectedConversation ? (
                <div className="h-full flex flex-col items-center justify-center text-slate-500 text-xs text-center px-4 space-y-2">
                  <MessageCircle className="h-10 w-10 text-slate-700 animate-pulse" />
                  <span>Select a session thread to view message records</span>
                </div>
              ) : isMsgsLoading ? (
                <div className="space-y-4">
                  {/* User loader */}
                  <div className="flex flex-col items-end space-y-1">
                    <div className="h-10 w-44 rounded-2xl bg-slate-900/80 animate-pulse" />
                    <div className="h-2 w-12 rounded bg-slate-800" />
                  </div>
                  {/* Assistant loader */}
                  <div className="flex flex-col items-start space-y-1">
                    <div className="h-16 w-64 rounded-2xl bg-slate-900/80 animate-pulse" />
                    <div className="h-2 w-16 rounded bg-slate-800" />
                  </div>
                </div>
              ) : messages.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center text-slate-500 text-xs py-10">
                  <span>No message logs found for this session</span>
                </div>
              ) : (
                messages.map((msg) => {
                  const isUser = msg.role === "user";
                  
                  return (
                    <div 
                      key={msg._id} 
                      className={`flex flex-col max-w-[85%] ${isUser ? "ml-auto items-end" : "mr-auto items-start"} animate-fadeIn`}
                    >
                      {/* Bubble */}
                      <div className={`p-3.5 rounded-2xl text-xs leading-relaxed ${
                        isUser 
                          ? "bg-violet-600/90 text-white rounded-br-none shadow-md shadow-violet-600/5" 
                          : "bg-slate-900 text-slate-100 border border-slate-800/80 rounded-bl-none shadow-md"
                      }`}>
                        {/* Message content */}
                        <p className="whitespace-pre-wrap font-sans break-words">{msg.content}</p>
                        
                        {/* Token Details if available (only on assistant replies, or whenever it exists) */}
                        {!isUser && (msg.total_tokens !== undefined || msg.response_time !== undefined) && (
                          <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[9px] text-slate-500 border-t border-slate-800/40 mt-2.5 pt-1.5 font-mono">
                            {msg.model && (
                              <span className="text-violet-400/90 font-semibold">{msg.model.split("/").pop()}</span>
                            )}
                            {msg.total_tokens && (
                              <span>Tokens: {msg.total_tokens} (P:{msg.prompt_tokens}/C:{msg.completion_tokens})</span>
                            )}
                            {msg.response_time && (
                              <span className="flex items-center gap-0.5 text-amber-500">
                                <Clock className="h-2.5 w-2.5 shrink-0" />
                                {msg.response_time}s
                              </span>
                            )}
                          </div>
                        )}
                      </div>
                      
                      {/* Metadata row */}
                      <div className="flex items-center gap-1.5 text-[9px] text-slate-500 mt-1 px-1 font-mono">
                        <span>{formatDate(msg.created_at)}</span>
                        {isUser && msg.total_tokens ? (
                          <>
                            <span>•</span>
                            <span>{msg.total_tokens} tkn</span>
                          </>
                        ) : null}
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>

        </section>

      </div>
    </div>
  );
}
