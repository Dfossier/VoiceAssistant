import React from 'react'
import { Cpu, HardDrive, Activity, Zap } from 'lucide-react'
import { SystemMetrics } from '../../hooks/useSystemStore'

interface SystemResourcesProps {
  metrics?: SystemMetrics | null
}

interface ResourceCardProps {
  icon: React.ReactNode
  title: string
  value: number
  unit: string
  max?: number
  color?: string
}

const ResourceCard: React.FC<ResourceCardProps> = ({ 
  icon, 
  title, 
  value, 
  unit, 
  max = 100,
  color = 'blue' 
}) => {
  const percentage = Math.min((value / max) * 100, 100)
  
  const colorClasses = {
    blue: 'text-blue-400 border-blue-500/20 bg-blue-500/10',
    green: 'text-green-400 border-green-500/20 bg-green-500/10',
    yellow: 'text-yellow-400 border-yellow-500/20 bg-yellow-500/10',
    red: 'text-red-400 border-red-500/20 bg-red-500/10',
  }
  
  const barColors = {
    blue: 'bg-blue-500',
    green: 'bg-green-500', 
    yellow: 'bg-yellow-500',
    red: 'bg-red-500',
  }
  
  // Determine color based on percentage
  let displayColor = color
  if (percentage > 80) displayColor = 'red'
  else if (percentage > 60) displayColor = 'yellow'
  else if (percentage > 0) displayColor = 'green'
  
  return (
    <div className={`p-3 rounded-lg border ${colorClasses[displayColor as keyof typeof colorClasses]}`}>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          {icon}
          <span className="text-sm font-medium">{title}</span>
        </div>
        <span className="text-lg font-bold">
          {value.toFixed(value < 10 ? 1 : 0)}{unit}
        </span>
      </div>
      
      <div className="w-full bg-gray-700 rounded-full h-2">
        <div
          className={`h-2 rounded-full transition-all duration-300 ${barColors[displayColor as keyof typeof barColors]}`}
          style={{ width: `${percentage}%` }}
        />
      </div>
      
      <div className="flex justify-between text-xs text-gray-400 mt-1">
        <span>0</span>
        <span>{max}{unit}</span>
      </div>
    </div>
  )
}

export const SystemResources: React.FC<SystemResourcesProps> = ({ metrics }) => {
  if (!metrics) {
    return (
      <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
        <h3 className="font-medium mb-3">System Resources</h3>
        <div className="space-y-3">
          <div className="animate-pulse">
            <div className="h-16 bg-gray-700 rounded-lg"></div>
          </div>
          <div className="animate-pulse">
            <div className="h-16 bg-gray-700 rounded-lg"></div>
          </div>
        </div>
      </div>
    )
  }
  
  return (
    <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
      <h3 className="font-medium mb-3">System Resources</h3>
      
      <div className="space-y-3">
        <ResourceCard
          icon={<Cpu className="w-4 h-4" />}
          title="CPU"
          value={metrics.cpu_percent}
          unit="%"
          color="blue"
        />
        
        <ResourceCard
          icon={<HardDrive className="w-4 h-4" />}
          title="Memory"
          value={metrics.memory_percent}
          unit="%"
          color="green"
        />
        
        {metrics.gpu_utilization !== undefined && (
          <ResourceCard
            icon={<Zap className="w-4 h-4" />}
            title="GPU"
            value={metrics.gpu_utilization}
            unit="%"
            color="yellow"
          />
        )}
        
        <ResourceCard
          icon={<Activity className="w-4 h-4" />}
          title="Connections"
          value={metrics.network_connections}
          unit=""
          max={1000}
          color="blue"
        />
      </div>
      
      {metrics.gpu_memory_mb && (
        <div className="mt-3 pt-3 border-t border-gray-700">
          <div className="flex justify-between text-sm text-gray-400">
            <span>GPU Memory</span>
            <span>{(metrics.gpu_memory_mb / 1024).toFixed(1)} GB</span>
          </div>
        </div>
      )}
    </div>
  )
}