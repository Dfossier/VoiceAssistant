import React from 'react'
import { Volume2 } from 'lucide-react'

interface AudioLevelMeterProps {
  level?: number // 0.0 to 1.0
}

export const AudioLevelMeter: React.FC<AudioLevelMeterProps> = ({ level = 0 }) => {
  // Convert level to dB for display
  const dB = level > 0 ? 20 * Math.log10(level) : -60
  const displaydB = Math.max(-60, Math.min(0, dB))
  
  // Generate meter segments
  const segments = 20
  const activeSegments = Math.floor((level * segments))
  
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Volume2 className="w-4 h-4 text-gray-400" />
          <span className="text-sm text-gray-400">Audio Level</span>
        </div>
        <span className="text-sm font-mono text-gray-400">
          {displaydB.toFixed(1)} dB
        </span>
      </div>
      
      <div className="flex gap-1 h-6">
        {Array.from({ length: segments }).map((_, i) => {
          const isActive = i < activeSegments
          const isYellow = i >= segments * 0.6 && i < segments * 0.85
          const isRed = i >= segments * 0.85
          
          let colorClass = 'bg-gray-700'
          if (isActive) {
            if (isRed) colorClass = 'bg-red-500'
            else if (isYellow) colorClass = 'bg-yellow-500'
            else colorClass = 'bg-green-500'
          }
          
          return (
            <div
              key={i}
              className={`flex-1 rounded-sm transition-colors duration-150 ${colorClass}`}
            />
          )
        })}
      </div>
      
      <div className="flex justify-between text-xs text-gray-500">
        <span>-60</span>
        <span>-30</span>
        <span>0</span>
      </div>
    </div>
  )
}