import { create } from 'zustand'

export interface ServiceStatus {
  name: string
  status: 'running' | 'stopped' | 'error'
  pid?: number
  uptime?: number
  cpu_percent?: number
  memory_mb?: number
  error?: string
}

export interface SystemStatus {
  backend: ServiceStatus
  discord_bot: ServiceStatus
  voice_pipeline: ServiceStatus
  claude_code_active: boolean
  terminals_active: number
  timestamp: string
}

export interface SystemMetrics {
  cpu_percent: number
  memory_percent: number
  gpu_utilization?: number
  gpu_memory_mb?: number
  network_connections: number
  audio_level?: number
  vad_confidence?: number
  pipeline_latency_ms?: number
}

interface SystemStore {
  status: SystemStatus | null
  metrics: SystemMetrics | null
  isConnected: boolean
  
  setStatus: (status: SystemStatus) => void
  updateMetrics: (metrics: SystemMetrics) => void
  setConnectionStatus: (connected: boolean) => void
}

export const useSystemStore = create<SystemStore>((set) => ({
  status: null,
  metrics: null,
  isConnected: false,
  
  setStatus: (status) => set({ status }),
  updateMetrics: (metrics) => set({ metrics }),
  setConnectionStatus: (connected) => set({ isConnected: connected }),
}))