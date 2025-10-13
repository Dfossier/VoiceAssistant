import React from 'react'
import { useSystemStore } from '../../hooks/useSystemStore'
import { Clock, Mic, Volume2, Brain } from 'lucide-react'

export const PipelineMetrics: React.FC = () => {
  const metrics = useSystemStore((state) => state.metrics)
  
  const MetricItem: React.FC<{
    icon: React.ReactNode
    label: string
    value: string
    status?: 'good' | 'warning' | 'error'
  }> = ({ icon, label, value, status = 'good' }) => {
    const statusColors = {
      good: 'text-green-400',
      warning: 'text-yellow-400',
      error: 'text-red-400',
    }
    
    return (
      <div className="flex items-center justify-between p-2 rounded border border-gray-700">
        <div className="flex items-center gap-2">
          {icon}
          <span className="text-sm text-gray-400">{label}</span>
        </div>
        <span className={`text-sm font-medium ${statusColors[status]}`}>
          {value}
        </span>
      </div>
    )
  }
  
  if (!metrics) {
    return (
      <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
        <h3 className="font-medium mb-3">Pipeline Metrics</h3>
        <div className="space-y-2">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="animate-pulse h-10 bg-gray-700 rounded"></div>
          ))}
        </div>
      </div>
    )
  }
  
  // Determine status based on latency
  const getLatencyStatus = (latency?: number): 'good' | 'warning' | 'error' => {
    if (!latency) return 'good'
    if (latency < 200) return 'good'
    if (latency < 500) return 'warning'
    return 'error'
  }
  
  // Determine VAD status
  const getVADStatus = (confidence?: number): 'good' | 'warning' | 'error' => {
    if (!confidence) return 'good'
    if (confidence > 0.7) return 'good'
    if (confidence > 0.3) return 'warning'
    return 'error'
  }
  
  // Determine audio status
  const getAudioStatus = (level?: number): 'good' | 'warning' | 'error' => {
    if (!level) return 'good'
    if (level < 0.01) return 'error'  // Too quiet
    if (level > 0.8) return 'warning'  // Too loud
    return 'good'
  }
  
  return (
    <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
      <h3 className="font-medium mb-3">Pipeline Metrics</h3>
      
      <div className="space-y-2">
        <MetricItem
          icon={<Clock className="w-4 h-4" />}
          label="Pipeline Latency"
          value={metrics.pipeline_latency_ms ? `${metrics.pipeline_latency_ms.toFixed(0)}ms` : '--'}
          status={getLatencyStatus(metrics.pipeline_latency_ms)}
        />
        
        <MetricItem
          icon={<Brain className="w-4 h-4" />}
          label="VAD Confidence"
          value={metrics.vad_confidence ? `${(metrics.vad_confidence * 100).toFixed(1)}%` : '--'}
          status={getVADStatus(metrics.vad_confidence)}
        />
        
        <MetricItem
          icon={<Mic className="w-4 h-4" />}
          label="Audio Level"
          value={metrics.audio_level ? `${(metrics.audio_level * 100).toFixed(1)}%` : '--'}
          status={getAudioStatus(metrics.audio_level)}
        />
        
        <MetricItem
          icon={<Volume2 className="w-4 h-4" />}
          label="Audio Quality"
          value={metrics.audio_level && metrics.audio_level > 0.01 ? 'Good' : 'Silent'}
          status={metrics.audio_level && metrics.audio_level > 0.01 ? 'good' : 'error'}
        />
      </div>
      
      <div className="mt-3 pt-3 border-t border-gray-700">
        <div className="text-xs text-gray-500 space-y-1">
          <div>• Latency: &lt;200ms Good, &lt;500ms Warning</div>
          <div>• VAD: &gt;70% Good, &gt;30% Warning</div>
          <div>• Audio: 1-80% range optimal</div>
        </div>
      </div>
    </div>
  )
}