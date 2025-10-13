import React from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Dashboard } from './components/dashboard/Dashboard'
import { useSystemStore } from './hooks/useSystemStore'
import { useWebSocket } from './hooks/useWebSocket'
import './App.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60000, // 1 minute
      refetchInterval: false, // Disable automatic refetching
      retry: false,
    },
  },
})

const WebSocketProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { setConnectionStatus } = useSystemStore()

  // Set as connected and do nothing else for now
  React.useEffect(() => {
    setConnectionStatus(true)
  }, [setConnectionStatus])

  return <>{children}</>
}

const ConnectionStatus: React.FC = () => {
  const isConnected = useSystemStore((state) => state.isConnected)
  
  return (
    <div className="flex items-center gap-2">
      <div
        className={`w-2 h-2 rounded-full ${
          isConnected ? 'bg-green-500' : 'bg-red-500'
        }`}
      />
      <span className="text-sm text-gray-400">
        {isConnected ? 'Connected' : 'Disconnected'}
      </span>
    </div>
  )
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <WebSocketProvider>
        <div className="min-h-screen bg-gray-900 text-white">
          <header className="bg-gray-800 border-b border-gray-700 px-6 py-4">
            <div className="flex items-center justify-between">
              <h1 className="text-xl font-bold">Voice Assistant Control Panel</h1>
              <div className="flex items-center gap-4">
                <ConnectionStatus />
                <span className="text-sm text-gray-400">
                  {new Date().toLocaleTimeString()}
                </span>
              </div>
            </div>
          </header>
          
          <main className="container mx-auto px-6 py-8">
            <Dashboard />
          </main>
        </div>
      </WebSocketProvider>
    </QueryClientProvider>
  )
}

export default App