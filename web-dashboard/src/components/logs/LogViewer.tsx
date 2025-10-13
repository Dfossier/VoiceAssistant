import React, { useState, useEffect, useRef } from 'react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts'
import { Download, Trash2, Search, RefreshCw, ArrowDown } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'

interface LogEntry {
  timestamp: string
  level: 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR'
  component: string
  message: string
}

interface LogsResponse {
  logs: string[] | LogEntry[]  // Can be either strings or structured log entries
}

interface LogSource {
  id: string
  name: string
  description: string
}

interface LogSourcesResponse {
  sources: LogSource[]
}

const fetchLogSources = async (): Promise<LogSourcesResponse> => {
  const response = await fetch('/api/system/logs/sources')
  if (!response.ok) throw new Error('Failed to fetch log sources')
  return response.json()
}

const fetchSystemLogs = async (source: string = 'backend'): Promise<LogsResponse> => {
  const response = await fetch(`/api/system/logs?source=${source}`)
  if (!response.ok) throw new Error('Failed to fetch logs')
  return response.json()
}

// Helper function to parse string logs into structured format
const parseLogEntry = (logString: string, index: number): LogEntry => {
  if (!logString || typeof logString !== 'string') {
    return {
      timestamp: new Date().toISOString(),
      level: 'INFO' as LogEntry['level'],
      component: 'system',
      message: 'Invalid log entry'
    }
  }
  
  // Try to extract timestamp, level, component from log string
  const timestampMatch = logString.match(/(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})/)
  const levelMatch = logString.match(/(DEBUG|INFO|WARNING|ERROR|WARN)/)
  const componentMatch = logString.match(/\|\s+([^:]+):\d+/)
  
  return {
    timestamp: timestampMatch?.[1] || new Date().toISOString(),
    level: (levelMatch?.[1] || 'INFO') as LogEntry['level'],
    component: componentMatch?.[1] || 'system',
    message: logString
  }
}

export const LogViewer: React.FC = () => {
  const [selectedSource, setSelectedSource] = useState('backend')
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [showAnalytics, setShowAnalytics] = useState(false)
  const [useWebSocket, setUseWebSocket] = useState(false)
  const [wsConnected, setWsConnected] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')
  const [levelFilter, setLevelFilter] = useState<string>('ALL')
  const [componentFilter, setComponentFilter] = useState<string>('ALL')
  const [autoScroll, setAutoScroll] = useState(true)
  const [isAtBottom, setIsAtBottom] = useState(true)
  
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const logContainerRef = useRef<HTMLDivElement>(null)
  
  const { data: sourcesData } = useQuery({
    queryKey: ['logSources'],
    queryFn: fetchLogSources,
  })
  
  const { data: logsData, isLoading, refetch } = useQuery({
    queryKey: ['systemLogs', selectedSource],
    queryFn: () => fetchSystemLogs(selectedSource),
    refetchInterval: autoRefresh && !useWebSocket ? 2000 : false,
  })
  
  // WebSocket connection management
  const disconnectWebSocket = () => {
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }
    setWsConnected(false)
  }
  
  useEffect(() => {
    if (!useWebSocket) {
      disconnectWebSocket()
      return
    }

    const connectWebSocket = () => {
      try {
        const ws = new WebSocket(`ws://${window.location.host}/ws/logs/${selectedSource}`)

        ws.onopen = () => {
          setWsConnected(true)
          console.log(`WebSocket connected for logs: ${selectedSource}`)
        }

        ws.onmessage = (event) => {
          try {
            const newLog = JSON.parse(event.data)
            // Update logs state with new real-time log
            // This would require lifting state up or using a different approach
            refetch() // For now, trigger a refetch to get updated logs
          } catch (error) {
            console.error('Failed to parse WebSocket log message:', error)
          }
        }

        ws.onclose = () => {
          setWsConnected(false)
          // Attempt to reconnect after 5 seconds
          reconnectTimeoutRef.current = setTimeout(() => {
            if (useWebSocket) connectWebSocket()
          }, 5000)
        }

        ws.onerror = (error) => {
          console.error('WebSocket error:', error)
          setWsConnected(false)
        }

        wsRef.current = ws
      } catch (error) {
        console.error('Failed to create WebSocket connection:', error)
        setUseWebSocket(false) // Fallback to polling
      }
    }

    connectWebSocket()

    return () => {
      disconnectWebSocket()
    }
  }, [selectedSource, useWebSocket, refetch])
  
  const sources = sourcesData?.sources || []
  const rawLogs = logsData?.logs || []
  
  // Convert string logs to structured format if needed
  const logs: LogEntry[] = (rawLogs || []).map((log, index) => {
    if (typeof log === 'string') {
      return parseLogEntry(log, index)
    }
    return log as LogEntry
  }).filter(Boolean) // Remove any null/undefined entries
  
  // Check if user is at bottom of scroll
  const checkIfAtBottom = () => {
    if (logContainerRef.current) {
      const { scrollTop, scrollHeight, clientHeight } = logContainerRef.current
      // Consider at bottom if within 50px (to account for rounding)
      const atBottom = scrollHeight - scrollTop - clientHeight < 50
      setIsAtBottom(atBottom)
    }
  }

  // Auto-scroll to bottom when new logs arrive, but only if already at bottom
  useEffect(() => {
    if (autoScroll && isAtBottom && logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight
    }
  }, [logs, autoScroll, isAtBottom])

  // Handle scroll events
  const handleScroll = () => {
    checkIfAtBottom()
  }

  const filteredLogs = (logs || []).filter(log => {
    const message = log.message || ''
    const component = log.component || ''
    const level = log.level || 'INFO'
    
    const matchesSearch = message.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         component.toLowerCase().includes(searchTerm.toLowerCase())
    const matchesLevel = levelFilter === 'ALL' || level === levelFilter
    const matchesComponent = componentFilter === 'ALL' || component === componentFilter
    
    return matchesSearch && matchesLevel && matchesComponent
  })

  const uniqueComponents = Array.from(new Set(logs.map(log => log.component || 'system').filter(Boolean)))
  
  // Syntax highlighting for log messages
  const highlightLogMessage = (message: string) => {
    if (!message) return message
    
    // Highlight JSON content
    const jsonMatch = message.match(/({.*})/)
    if (jsonMatch) {
      const before = message.substring(0, jsonMatch.index)
      const after = message.substring(jsonMatch.index! + jsonMatch[0].length)
      try {
        const formattedJson = JSON.stringify(JSON.parse(jsonMatch[1]), null, 2)
        return (
          <span>
            {before}
            <span className="bg-gray-800 p-1 rounded text-green-400 font-mono text-xs">
              {formattedJson}
            </span>
            {after}
          </span>
        )
      } catch {
        // Not valid JSON, continue
      }
    }
    
    // Highlight error keywords
    const errorPatterns = [
      /\b(error|exception|failed|failure)\b/gi,
      /\b(timeout|connection refused|not found)\b/gi,
      /\b(null|undefined|nan)\b/gi
    ]
    
    let highlighted = message
    errorPatterns.forEach(pattern => {
      highlighted = highlighted.replace(pattern, (match) => 
        `<span class="text-red-400 font-semibold">${match}</span>`
      )
    })
    
    // Highlight numbers
    highlighted = highlighted.replace(/\b(\d+)\b/g, '<span class="text-blue-400">$1</span>')
    
    // Highlight URLs
    highlighted = highlighted.replace(/(https?:\/\/[^\s]+)/g, '<span class="text-cyan-400">$1</span>')
    
    return <span dangerouslySetInnerHTML={{ __html: highlighted }} />
  }
  
  // Analytics computation
  const analytics = React.useMemo(() => {
    const levelCounts = { DEBUG: 0, INFO: 0, WARNING: 0, ERROR: 0 }
    const componentCounts: Record<string, number> = {}
    const hourlyErrors: Record<string, number> = {}
    
    logs.forEach(log => {
      // Count by level
      const level = log.level || 'INFO'
      levelCounts[level as keyof typeof levelCounts] = (levelCounts[level as keyof typeof levelCounts] || 0) + 1
      
      // Count by component
      const component = log.component || 'system'
      componentCounts[component] = (componentCounts[component] || 0) + 1
      
      // Count errors by hour
      if (level === 'ERROR') {
        const hour = new Date(log.timestamp || Date.now()).getHours().toString().padStart(2, '0')
        hourlyErrors[hour] = (hourlyErrors[hour] || 0) + 1
      }
    })
    
    return {
      levelCounts,
      componentCounts,
      hourlyErrors,
      totalLogs: logs.length,
      errorRate: logs.length > 0 ? (levelCounts.ERROR / logs.length * 100).toFixed(1) : '0.0'
    }
  }, [logs])
  
  // Prepare chart data
  const levelChartData = Object.entries(analytics.levelCounts).map(([level, count]) => ({
    level,
    count,
    fill: level === 'ERROR' ? '#ef4444' : level === 'WARNING' ? '#f59e0b' : level === 'INFO' ? '#3b82f6' : '#6b7280'
  }))
  
  const hourlyErrorData = Object.entries(analytics.hourlyErrors).map(([hour, count]) => ({
    hour: `${hour}:00`,
    errors: count
  }))

  const getLevelColor = (level: LogEntry['level']) => {
    switch (level) {
      case 'ERROR': return 'text-red-400'
      case 'WARNING': return 'text-yellow-400'
      case 'INFO': return 'text-blue-400'
      case 'DEBUG': return 'text-gray-400'
      default: return 'text-gray-300'
    }
  }

  const handleExport = () => {
    const logText = filteredLogs.map(log => 
      `[${log.timestamp}] ${log.level} ${log.component}: ${log.message}`
    ).join('\n')
    
    const blob = new Blob([logText], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `logs-${new Date().toISOString().slice(0, 10)}.txt`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">System Logs</h2>
        
        <div className="flex gap-2">
          <button
            onClick={() => refetch()}
            disabled={isLoading}
            className="flex items-center gap-2 px-3 py-2 text-sm bg-green-600 hover:bg-green-700 disabled:bg-gray-600 rounded-lg transition-colors"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
          
          <button
            onClick={() => setShowAnalytics(!showAnalytics)}
            className={`flex items-center gap-2 px-3 py-2 text-sm rounded-lg transition-colors ${showAnalytics ? 'bg-purple-600 hover:bg-purple-700' : 'bg-gray-600 hover:bg-gray-700'}`}
          >
            📊 Analytics
          </button>
          
          <button
            onClick={handleExport}
            className="flex items-center gap-2 px-3 py-2 text-sm bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors"
          >
            <Download className="w-4 h-4" />
            Export
          </button>
        </div>
      </div>
      
      {/* Analytics Dashboard */}
      {showAnalytics && (
        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700 space-y-6">
          <h3 className="text-lg font-semibold">Log Analytics</h3>
          
          {/* Key Metrics */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="bg-gray-900 p-4 rounded-lg">
              <div className="text-2xl font-bold text-blue-400">{analytics.totalLogs}</div>
              <div className="text-sm text-gray-400">Total Logs</div>
            </div>
            <div className="bg-gray-900 p-4 rounded-lg">
              <div className="text-2xl font-bold text-red-400">{analytics.levelCounts.ERROR}</div>
              <div className="text-sm text-gray-400">Errors</div>
            </div>
            <div className="bg-gray-900 p-4 rounded-lg">
              <div className="text-2xl font-bold text-yellow-400">{analytics.levelCounts.WARNING}</div>
              <div className="text-sm text-gray-400">Warnings</div>
            </div>
            <div className="bg-gray-900 p-4 rounded-lg">
              <div className="text-2xl font-bold text-green-400">{analytics.errorRate}%</div>
              <div className="text-sm text-gray-400">Error Rate</div>
            </div>
          </div>
          
          {/* Charts */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Log Level Distribution */}
            <div className="bg-gray-900 p-4 rounded-lg">
              <h4 className="text-md font-semibold mb-4">Log Level Distribution</h4>
              <ResponsiveContainer width="100%" height={200}>
                <PieChart>
                  <Pie
                    data={levelChartData}
                    dataKey="count"
                    nameKey="level"
                    cx="50%"
                    cy="50%"
                    outerRadius={60}
                    label={({ level, count }) => `${level}: ${count}`}
                  >
                    {levelChartData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.fill} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            </div>
            
            {/* Hourly Error Trends */}
            <div className="bg-gray-900 p-4 rounded-lg">
              <h4 className="text-md font-semibold mb-4">Hourly Error Trends</h4>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={hourlyErrorData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                  <XAxis dataKey="hour" stroke="#9ca3af" />
                  <YAxis stroke="#9ca3af" />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#1f2937', border: 'none', borderRadius: '0.5rem' }}
                    labelStyle={{ color: '#f3f4f6' }}
                  />
                  <Bar dataKey="errors" fill="#ef4444" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="bg-gray-800 rounded-lg p-4 border border-gray-700 space-y-3">
        <div className="flex gap-4 flex-wrap">
          <div className="flex-1 min-w-0">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                type="text"
                placeholder="Search logs..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-10 pr-3 py-2 bg-gray-700 border border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
          </div>
          
          <select
            value={selectedSource}
            onChange={(e) => setSelectedSource(e.target.value)}
            className="px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500"
          >
            {Array.isArray(sourcesData?.sources) ? 
              sourcesData.sources.map(source => (
                <option key={typeof source === 'string' ? source : source.id} value={typeof source === 'string' ? source : source.id}>
                  {typeof source === 'string' ? source : source.name}
                </option>
              )) :
              ['backend', 'discord', 'voice', 'system'].map(source => (
                <option key={source} value={source}>{source}</option>
              ))
            }
          </select>
          
          <select
            value={levelFilter}
            onChange={(e) => setLevelFilter(e.target.value)}
            className="px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500"
          >
            <option value="ALL">All Levels</option>
            <option value="ERROR">Error</option>
            <option value="WARNING">Warning</option>
            <option value="INFO">Info</option>
            <option value="DEBUG">Debug</option>
          </select>
          
          <select
            value={componentFilter}
            onChange={(e) => setComponentFilter(e.target.value)}
            className="px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500"
          >
            <option value="ALL">All Components</option>
            {uniqueComponents.map(component => (
              <option key={component} value={component}>{component}</option>
            ))}
          </select>
        </div>
        
        <div className="flex items-center gap-4">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={autoScroll}
              onChange={(e) => setAutoScroll(e.target.checked)}
              className="rounded border-gray-600 bg-gray-700 text-blue-600 focus:ring-blue-500"
            />
            Auto-scroll
            {autoScroll && !isAtBottom && (
              <span className="text-yellow-500 text-xs">(paused)</span>
            )}
          </label>
          
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              className="rounded border-gray-600 bg-gray-700 text-green-600 focus:ring-green-500"
            />
            Auto-refresh (2s)
          </label>
          
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={useWebSocket}
              onChange={(e) => setUseWebSocket(e.target.checked)}
              className="rounded border-gray-600 bg-gray-700 text-blue-600 focus:ring-blue-500"
            />
            Real-time WebSocket
            {wsConnected ? (
              <span className="text-green-500 text-xs">(connected)</span>
            ) : useWebSocket ? (
              <span className="text-yellow-500 text-xs">(connecting...)</span>
            ) : null}
          </label>
        </div>
      </div>

      {/* Logs Container */}
      <div className="bg-gray-800 rounded-lg border border-gray-700 relative">
        <div
          ref={logContainerRef}
          onScroll={handleScroll}
          className="h-96 overflow-y-auto custom-scrollbar"
        >
          {isLoading ? (
            <div className="flex items-center justify-center h-full text-gray-500">
              <RefreshCw className="w-8 h-8 animate-spin" />
            </div>
          ) : filteredLogs.length === 0 ? (
            <div className="flex items-center justify-center h-full text-gray-500">
              {logs.length === 0 ? 'No logs available' : 'No logs match the current filters'}
            </div>
          ) : (
            <div className="h-96 overflow-y-auto p-4 space-y-1">
              {(filteredLogs || []).map((log, index) => (
                <div
                  key={`${selectedSource}-${index}-${log?.timestamp || index}`}
                  className="flex gap-3 hover:bg-gray-800 px-2 py-1 rounded pr-4"
                >
                  <span className="text-gray-500 whitespace-nowrap">
                    {log?.timestamp || ''}
                  </span>
                  <span className={`font-medium w-16 text-center ${getLevelColor(log?.level || 'INFO')}`}>
                    {log?.level || 'INFO'}
                  </span>
                  <span className="text-purple-400 w-20 text-center">
                    {log?.component || 'system'}
                  </span>
                  <span className="text-gray-300 flex-1">
                    {highlightLogMessage(log?.message || '')}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
        
        {/* Scroll to bottom button */}
        {!isAtBottom && (
          <button
            onClick={() => {
              if (logContainerRef.current) {
                logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight
              }
            }}
            className="absolute bottom-4 right-4 p-2 bg-blue-600 hover:bg-blue-700 rounded-full shadow-lg transition-all transform hover:scale-110"
            title="Scroll to bottom"
          >
            <ArrowDown className="w-5 h-5" />
          </button>
        )}
      </div>
    </div>
  )
}