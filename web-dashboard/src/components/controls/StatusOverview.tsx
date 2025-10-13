import React, { useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Activity, Server, MessageCircle, Terminal } from 'lucide-react'
import { useSystemStore, SystemStatus } from '../../hooks/useSystemStore'

const fetchSystemStatus = async (): Promise<SystemStatus> => {
  const response = await fetch('/api/system/status')
  if (!response.ok) throw new Error('Failed to fetch status')
  return response.json()
}

const StatusCard: React.FC<{
  icon: React.ReactNode
  title: string
  status: 'running' | 'stopped' | 'starting' | 'stopping' | 'error'
  details?: string
}> = ({ icon, title, status, details }) => {
  const statusColors = {
    running: 'bg-green-500',
    stopped: 'bg-gray-500',
    starting: 'bg-blue-500 animate-pulse',
    stopping: 'bg-yellow-500 animate-pulse',
    error: 'bg-red-500',
  }

  const statusText = {
    running: 'Running',
    stopped: 'Stopped',
    starting: 'Starting...',
    stopping: 'Stopping...',
    error: 'Error',
  }

  return (
    <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          {icon}
          <h3 className="font-medium">{title}</h3>
        </div>
        <span className={`w-3 h-3 rounded-full ${statusColors[status]}`}></span>
      </div>
      <p className="text-sm text-gray-400">{statusText[status]}</p>
      {details && <p className="text-xs text-gray-500 mt-1">{details}</p>}
    </div>
  )
}

export const StatusOverview: React.FC = () => {
  const { setStatus } = useSystemStore()
  
  const { data: status, isLoading } = useQuery({
    queryKey: ['systemStatus'],
    queryFn: fetchSystemStatus,
    refetchInterval: false, // Disable automatic polling
  })

  useEffect(() => {
    if (status) {
      setStatus(status)
    }
  }, [status, setStatus])

  if (isLoading) {
    return (
      <div className="space-y-4">
        <h2 className="text-lg font-semibold">System Status</h2>
        <div className="animate-pulse space-y-3">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="bg-gray-800 h-20 rounded-lg"></div>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold">System Status</h2>
      
      <StatusCard
        icon={<Server className="w-5 h-5" />}
        title="Backend"
        status={status?.backend?.status || 'stopped'}
        details={status?.backend?.status === 'running' 
          ? `Port: 8000 • Uptime: ${Math.floor((status.backend.uptime || 0) / 60)}m`
          : undefined}
      />

      <StatusCard
        icon={<Activity className="w-5 h-5" />}
        title="Voice Pipeline"
        status={status?.voice_pipeline?.status || 'stopped'}
        details={status?.voice_pipeline?.status === 'running'
          ? `STT/TTS: Ready`
          : undefined}
      />

      <StatusCard
        icon={<MessageCircle className="w-5 h-5" />}
        title="Discord Bot"
        status={status?.discord_bot?.status || 'stopped'}
        details={status?.discord_bot?.status === 'running'
          ? `Voice: Ready`
          : undefined}
      />

      <StatusCard
        icon={<Activity className="w-5 h-5" />}
        title="Claude Code"
        status={status?.claude_code_active ? 'running' : 'stopped'}
        details={status?.claude_code_active
          ? `${status?.terminals_active || 0} terminals`
          : 'No active session'}
      />

      <StatusCard
        icon={<Terminal className="w-5 h-5" />}
        title="Terminals"
        status={status && status.terminals_active > 0 ? 'running' : 'stopped'}
        details={`${status?.terminals_active || 0} active`}
      />
    </div>
  )
}