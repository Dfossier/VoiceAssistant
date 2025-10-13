import React, { useEffect, useRef } from 'react'
import { useSystemStore } from '../../hooks/useSystemStore'

interface DataPoint {
  timestamp: number
  latency: number
  cpu: number
  memory: number
}

export const PerformanceChart: React.FC = () => {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const dataRef = useRef<DataPoint[]>([])
  const metrics = useSystemStore((state) => state.metrics)
  
  // Add new data point when metrics update
  useEffect(() => {
    if (!metrics) return
    
    const now = Date.now()
    const newPoint: DataPoint = {
      timestamp: now,
      latency: metrics.pipeline_latency_ms || 0,
      cpu: metrics.cpu_percent,
      memory: metrics.memory_percent,
    }
    
    dataRef.current.push(newPoint)
    
    // Keep last 60 seconds of data
    const cutoff = now - 60000
    dataRef.current = dataRef.current.filter(p => p.timestamp > cutoff)
    
    drawChart()
  }, [metrics])
  
  const drawChart = () => {
    const canvas = canvasRef.current
    if (!canvas) return
    
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    
    const { width, height } = canvas
    const data = dataRef.current
    
    // Clear canvas
    ctx.fillStyle = '#1f2937'
    ctx.fillRect(0, 0, width, height)
    
    if (data.length < 2) return
    
    const margin = 20
    const chartWidth = width - 2 * margin
    const chartHeight = height - 2 * margin
    
    // Draw grid
    ctx.strokeStyle = '#374151'
    ctx.lineWidth = 1
    
    // Vertical grid lines
    for (let i = 0; i <= 10; i++) {
      const x = margin + (i / 10) * chartWidth
      ctx.beginPath()
      ctx.moveTo(x, margin)
      ctx.lineTo(x, height - margin)
      ctx.stroke()
    }
    
    // Horizontal grid lines
    for (let i = 0; i <= 5; i++) {
      const y = margin + (i / 5) * chartHeight
      ctx.beginPath()
      ctx.moveTo(margin, y)
      ctx.lineTo(width - margin, y)
      ctx.stroke()
    }
    
    // Draw latency line (scale: 0-500ms)
    if (data.some(d => d.latency > 0)) {
      ctx.strokeStyle = '#10b981'
      ctx.lineWidth = 2
      ctx.beginPath()
      
      data.forEach((point, i) => {
        const x = margin + (i / (data.length - 1)) * chartWidth
        const y = height - margin - (point.latency / 500) * chartHeight
        
        if (i === 0) ctx.moveTo(x, y)
        else ctx.lineTo(x, y)
      })
      
      ctx.stroke()
    }
    
    // Draw CPU line (scale: 0-100%)
    ctx.strokeStyle = '#3b82f6'
    ctx.lineWidth = 2
    ctx.beginPath()
    
    data.forEach((point, i) => {
      const x = margin + (i / (data.length - 1)) * chartWidth
      const y = height - margin - (point.cpu / 100) * chartHeight
      
      if (i === 0) ctx.moveTo(x, y)
      else ctx.lineTo(x, y)
    })
    
    ctx.stroke()
    
    // Draw memory line (scale: 0-100%)
    ctx.strokeStyle = '#f59e0b'
    ctx.lineWidth = 2
    ctx.beginPath()
    
    data.forEach((point, i) => {
      const x = margin + (i / (data.length - 1)) * chartWidth
      const y = height - margin - (point.memory / 100) * chartHeight
      
      if (i === 0) ctx.moveTo(x, y)
      else ctx.lineTo(x, y)
    })
    
    ctx.stroke()
  }
  
  // Initial draw
  useEffect(() => {
    drawChart()
  }, [])
  
  return (
    <div className="space-y-3">
      <canvas
        ref={canvasRef}
        width={400}
        height={200}
        className="w-full h-48 rounded border border-gray-700"
      />
      
      <div className="flex justify-center gap-6 text-sm">
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 bg-green-500 rounded"></div>
          <span className="text-gray-400">Latency (ms)</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 bg-blue-500 rounded"></div>
          <span className="text-gray-400">CPU (%)</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 bg-yellow-500 rounded"></div>
          <span className="text-gray-400">Memory (%)</span>
        </div>
      </div>
    </div>
  )
}