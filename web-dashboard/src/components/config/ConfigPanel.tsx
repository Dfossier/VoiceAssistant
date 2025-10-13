import React, { useState } from 'react'
import { Settings, Save, RotateCcw } from 'lucide-react'

interface ConfigItem {
  key: string
  label: string
  value: string | number | boolean
  type: 'text' | 'number' | 'boolean' | 'select'
  options?: string[]
  description?: string
}

const defaultConfig: ConfigItem[] = [
  {
    key: 'whisper_model',
    label: 'Whisper Model',
    value: 'small',
    type: 'select',
    options: ['tiny', 'small', 'medium', 'large'],
    description: 'STT model size (larger = better accuracy, more VRAM)'
  },
  {
    key: 'llm_model',
    label: 'LLM Model',
    value: 'phi-3-mini',
    type: 'select',
    options: ['phi-3-mini', 'smollm2', 'qwen2.5'],
    description: 'Language model for conversation'
  },
  {
    key: 'tts_voice',
    label: 'TTS Voice',
    value: 'kokoro',
    type: 'select',
    options: ['kokoro', 'espeak'],
    description: 'Text-to-speech voice engine'
  },
  {
    key: 'vad_threshold',
    label: 'VAD Threshold',
    value: 0.5,
    type: 'number',
    description: 'Voice activity detection sensitivity (0.0-1.0)'
  },
  {
    key: 'auto_interruption',
    label: 'Auto Interruption',
    value: true,
    type: 'boolean',
    description: 'Allow interrupting AI responses'
  },
  {
    key: 'max_response_time',
    label: 'Max Response Time (s)',
    value: 30,
    type: 'number',
    description: 'Maximum time to wait for AI response'
  },
  {
    key: 'log_level',
    label: 'Log Level',
    value: 'INFO',
    type: 'select',
    options: ['DEBUG', 'INFO', 'WARNING', 'ERROR'],
    description: 'System logging verbosity'
  }
]

export const ConfigPanel: React.FC = () => {
  const [config, setConfig] = useState<ConfigItem[]>(defaultConfig)
  const [hasChanges, setHasChanges] = useState(false)
  const [saving, setSaving] = useState(false)

  const updateConfigValue = (key: string, value: string | number | boolean) => {
    setConfig(prev => prev.map(item => 
      item.key === key ? { ...item, value } : item
    ))
    setHasChanges(true)
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      // TODO: Implement API call to save config
      const configData = config.reduce((acc, item) => {
        acc[item.key] = item.value
        return acc
      }, {} as Record<string, any>)
      
      console.log('Saving config:', configData)
      
      // Simulate API call
      await new Promise(resolve => setTimeout(resolve, 1000))
      
      setHasChanges(false)
    } catch (error) {
      console.error('Failed to save config:', error)
    } finally {
      setSaving(false)
    }
  }

  const handleReset = () => {
    setConfig(defaultConfig)
    setHasChanges(true)
  }

  const renderConfigInput = (item: ConfigItem) => {
    switch (item.type) {
      case 'boolean':
        return (
          <label className="flex items-center">
            <input
              type="checkbox"
              checked={item.value as boolean}
              onChange={(e) => updateConfigValue(item.key, e.target.checked)}
              className="rounded border-gray-600 bg-gray-700 text-blue-600 focus:ring-blue-500"
            />
            <span className="ml-2 text-sm">Enabled</span>
          </label>
        )

      case 'select':
        return (
          <select
            value={item.value as string}
            onChange={(e) => updateConfigValue(item.key, e.target.value)}
            className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          >
            {item.options?.map(option => (
              <option key={option} value={option}>{option}</option>
            ))}
          </select>
        )

      case 'number':
        return (
          <input
            type="number"
            value={item.value as number}
            onChange={(e) => updateConfigValue(item.key, parseFloat(e.target.value))}
            className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            step={item.key === 'vad_threshold' ? '0.1' : '1'}
            min={item.key === 'vad_threshold' ? '0' : undefined}
            max={item.key === 'vad_threshold' ? '1' : undefined}
          />
        )

      default:
        return (
          <input
            type="text"
            value={item.value as string}
            onChange={(e) => updateConfigValue(item.key, e.target.value)}
            className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        )
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold flex items-center gap-2">
          <Settings className="w-5 h-5" />
          Configuration
        </h2>
        
        <div className="flex gap-2">
          <button
            onClick={handleReset}
            className="flex items-center gap-2 px-3 py-2 text-sm bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors"
          >
            <RotateCcw className="w-4 h-4" />
            Reset
          </button>
          
          <button
            onClick={handleSave}
            disabled={!hasChanges || saving}
            className="flex items-center gap-2 px-4 py-2 text-sm bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg transition-colors"
          >
            <Save className="w-4 h-4" />
            {saving ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>

      <div className="space-y-4">
        {config.map((item) => (
          <div key={item.key} className="bg-gray-800 rounded-lg p-4 border border-gray-700">
            <div className="space-y-2">
              <label className="block text-sm font-medium">
                {item.label}
              </label>
              
              {renderConfigInput(item)}
              
              {item.description && (
                <p className="text-xs text-gray-500">{item.description}</p>
              )}
            </div>
          </div>
        ))}
      </div>

      {hasChanges && (
        <div className="bg-yellow-500/10 border border-yellow-500/20 rounded-lg p-3">
          <p className="text-sm text-yellow-400">
            ⚠️ You have unsaved changes. Click "Save" to apply them.
          </p>
        </div>
      )}
    </div>
  )
}