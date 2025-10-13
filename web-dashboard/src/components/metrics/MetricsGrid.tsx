import React from 'react'
import { useSystemStore } from '../../hooks/useSystemStore'
import { AudioLevelMeter } from './AudioLevelMeter'
import { PerformanceChart } from './PerformanceChart'
import { PipelineMetrics } from './PipelineMetrics'
import { SystemResources } from './SystemResources'

export const MetricsGrid: React.FC = () => {
  const metrics = useSystemStore((state) => state.metrics)

  return (
    <div className="h-full space-y-6">
      <h2 className="text-lg font-semibold">Real-Time Metrics</h2>
      
      {/* Audio Processing Panel */}
      <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
        <h3 className="font-medium mb-3">Audio Processing</h3>
        <div className="space-y-4">
          <AudioLevelMeter level={metrics?.audio_level} />
          
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-sm text-gray-400">VAD Confidence</p>
              <div className="mt-1 h-2 bg-gray-700 rounded-full overflow-hidden">
                <div 
                  className="h-full bg-green-500 transition-all duration-150"
                  style={{ width: `${(metrics?.vad_confidence || 0) * 100}%` }}
                />
              </div>
              <p className="text-xs text-gray-500 mt-1">
                {((metrics?.vad_confidence || 0) * 100).toFixed(1)}%
              </p>
            </div>
            
            <div>
              <p className="text-sm text-gray-400">Pipeline Latency</p>
              <p className="text-2xl font-bold">
                {metrics?.pipeline_latency_ms?.toFixed(0) || '--'} 
                <span className="text-sm font-normal text-gray-400">ms</span>
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Performance Charts */}
      <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
        <h3 className="font-medium mb-3">Pipeline Performance</h3>
        <PerformanceChart />
      </div>

      {/* System Resources */}
      <div className="grid grid-cols-2 gap-4">
        <SystemResources metrics={metrics} />
        <PipelineMetrics />
      </div>
    </div>
  )
}