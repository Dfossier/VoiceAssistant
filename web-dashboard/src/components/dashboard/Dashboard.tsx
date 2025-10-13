import React, { useState } from 'react'
import { StatusOverview } from '../controls/StatusOverview'
import { QuickActions } from '../controls/QuickActions'
import { MetricsGrid } from '../metrics/MetricsGrid'
import { ConfigPanel } from '../config/ConfigPanel'
import { LogViewer } from '../logs/LogViewer'
import { Activity, Settings, FileText } from 'lucide-react'

type TabType = 'overview' | 'config' | 'logs'

export const Dashboard: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabType>('overview')

  const tabs = [
    { id: 'overview' as const, label: 'Overview', icon: Activity },
    { id: 'config' as const, label: 'Configuration', icon: Settings },
    { id: 'logs' as const, label: 'Logs', icon: FileText },
  ]

  const renderTabContent = () => {
    switch (activeTab) {
      case 'overview':
        return (
          <div className="h-full grid grid-cols-12 gap-6">
            {/* Left Column - Status & Controls */}
            <div className="col-span-4 space-y-6">
              <StatusOverview />
              <QuickActions />
            </div>

            {/* Right Column - Metrics */}
            <div className="col-span-8">
              <MetricsGrid />
            </div>
          </div>
        )
      case 'config':
        return (
          <div className="max-w-4xl mx-auto">
            <ConfigPanel />
          </div>
        )
      case 'logs':
        return (
          <div className="h-full">
            <LogViewer />
          </div>
        )
      default:
        return null
    }
  }

  return (
    <div className="space-y-6">
      {/* Tab navigation */}
      <nav className="border-b border-gray-700">
        <div className="flex space-x-8">
          {tabs.map((tab) => {
            const Icon = tab.icon
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
                  activeTab === tab.id
                    ? 'border-blue-500 text-blue-400'
                    : 'border-transparent text-gray-400 hover:text-gray-300 hover:border-gray-300'
                }`}
              >
                <Icon className="w-4 h-4" />
                {tab.label}
              </button>
            )
          })}
        </div>
      </nav>

      {/* Tab content */}
      <div className="min-h-[600px]">
        {renderTabContent()}
      </div>
    </div>
  )
}