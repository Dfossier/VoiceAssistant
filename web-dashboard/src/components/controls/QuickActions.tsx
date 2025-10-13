import React, { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Play, Square, RefreshCw, Download, Settings, Wifi } from 'lucide-react'

interface ActionButtonProps {
  icon: React.ReactNode
  label: string
  onClick: () => void
  variant?: 'primary' | 'secondary' | 'danger'
  disabled?: boolean
  loading?: boolean
}

const ActionButton: React.FC<ActionButtonProps> = ({ 
  icon, 
  label, 
  onClick, 
  variant = 'secondary', 
  disabled = false,
  loading = false 
}) => {
  const baseClasses = 'flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed'
  const variantClasses = {
    primary: 'bg-blue-600 hover:bg-blue-700 text-white',
    secondary: 'bg-gray-700 hover:bg-gray-600 text-gray-100',
    danger: 'bg-red-600 hover:bg-red-700 text-white',
  }

  return (
    <button
      className={`${baseClasses} ${variantClasses[variant]}`}
      onClick={onClick}
      disabled={disabled || loading}
    >
      {loading ? (
        <RefreshCw className="w-4 h-4 animate-spin" />
      ) : (
        icon
      )}
      <span>{label}</span>
    </button>
  )
}

const controlService = async ({ action, service }: { action: string; service: string }) => {
  const response = await fetch('/api/system/control', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action, service }),
  })
  if (!response.ok) throw new Error('Failed to control service')
  return response.json()
}

export const QuickActions: React.FC = () => {
  const queryClient = useQueryClient()
  const [activeAction, setActiveAction] = useState<string | null>(null)

  const controlMutation = useMutation({
    mutationFn: controlService,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['systemStatus'] })
      setActiveAction(null)
    },
    onError: (error) => {
      console.error('Control error:', error)
      setActiveAction(null)
    },
  })

  const handleAction = (action: string, service: string) => {
    setActiveAction(`${action}-${service}`)
    controlMutation.mutate({ action, service })
  }

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold">Service Controls</h2>
      
      {/* Backend Controls */}
      <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
        <h3 className="font-medium mb-3 flex items-center gap-2">
          <span>Backend Service</span>
        </h3>
        <div className="grid grid-cols-3 gap-2">
          <ActionButton
            icon={<Play className="w-4 h-4" />}
            label="Start"
            onClick={() => handleAction('start', 'backend')}
            variant="primary"
            loading={activeAction === 'start-backend'}
          />
          <ActionButton
            icon={<Square className="w-4 h-4" />}
            label="Stop"
            onClick={() => handleAction('stop', 'backend')}
            variant="danger"
            loading={activeAction === 'stop-backend'}
          />
          <ActionButton
            icon={<RefreshCw className="w-4 h-4" />}
            label="Restart"
            onClick={() => handleAction('restart', 'backend')}
            loading={activeAction === 'restart-backend'}
          />
        </div>
      </div>

      {/* Voice Pipeline Controls */}
      <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
        <h3 className="font-medium mb-3 flex items-center gap-2">
          <span>Voice Pipeline</span>
        </h3>
        <div className="grid grid-cols-3 gap-2">
          <ActionButton
            icon={<Play className="w-4 h-4" />}
            label="Start"
            onClick={() => handleAction('start', 'voice')}
            variant="primary"
            loading={activeAction === 'start-voice'}
          />
          <ActionButton
            icon={<Square className="w-4 h-4" />}
            label="Stop"
            onClick={() => handleAction('stop', 'voice')}
            variant="danger"
            loading={activeAction === 'stop-voice'}
          />
          <ActionButton
            icon={<RefreshCw className="w-4 h-4" />}
            label="Restart"
            onClick={() => handleAction('restart', 'voice')}
            loading={activeAction === 'restart-voice'}
          />
        </div>
      </div>

      {/* Discord Bot Controls */}
      <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
        <h3 className="font-medium mb-3 flex items-center gap-2">
          <span>Discord Bot</span>
        </h3>
        <div className="grid grid-cols-3 gap-2">
          <ActionButton
            icon={<Play className="w-4 h-4" />}
            label="Start"
            onClick={() => handleAction('start', 'bot')}
            variant="primary"
            loading={activeAction === 'start-bot'}
          />
          <ActionButton
            icon={<Square className="w-4 h-4" />}
            label="Stop"
            onClick={() => handleAction('stop', 'bot')}
            variant="danger"
            loading={activeAction === 'stop-bot'}
          />
          <ActionButton
            icon={<RefreshCw className="w-4 h-4" />}
            label="Restart"
            onClick={() => handleAction('restart', 'bot')}
            loading={activeAction === 'restart-bot'}
          />
        </div>
      </div>

      {/* System Actions */}
      <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
        <h3 className="font-medium mb-3">System Actions</h3>
        <div className="space-y-2">
          <ActionButton
            icon={<Play className="w-4 h-4" />}
            label="Start All Services"
            onClick={() => handleAction('start', 'all')}
            variant="primary"
            loading={activeAction === 'start-all'}
          />
          <ActionButton
            icon={<Square className="w-4 h-4" />}
            label="Stop All Services"
            onClick={() => handleAction('stop', 'all')}
            variant="danger"
            loading={activeAction === 'stop-all'}
          />
        </div>
      </div>

      {/* Utility Actions */}
      <div className="pt-2 border-t border-gray-700 space-y-2">
        <ActionButton
          icon={<Download className="w-4 h-4" />}
          label="Export Logs"
          onClick={() => window.open('/api/logs/export', '_blank')}
        />
        
        <ActionButton
          icon={<Wifi className="w-4 h-4" />}
          label="Test Connection"
          onClick={() => console.log('Test connection')}
        />
      </div>
    </div>
  )
}