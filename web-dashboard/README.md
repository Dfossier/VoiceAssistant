# Voice Assistant Web Control Panel

A React TypeScript dashboard for monitoring and controlling the voice assistant system.

## Features

- **System Status**: Real-time monitoring of backend and Discord bot status
- **Quick Actions**: Start, stop, restart system components
- **Live Metrics**: Audio levels, VAD confidence, pipeline latency, system resources
- **Configuration**: Adjust whisper model, LLM settings, VAD thresholds
- **Log Viewer**: Real-time system logs with filtering and export

## Setup

1. Install dependencies:
```bash
npm install
```

2. Start development server:
```bash
npm run dev
```

3. Build for production:
```bash
npm run build
```

## Architecture

- **Frontend**: React 18 + TypeScript + Vite
- **Styling**: Tailwind CSS with dark theme
- **State Management**: Zustand
- **Data Fetching**: TanStack Query (React Query)  
- **Real-time**: WebSocket for metrics streaming
- **Icons**: Lucide React

## API Integration

The dashboard connects to the backend API at `http://localhost:8000`:

- **REST Endpoints**: System control, status, configuration
- **WebSocket**: Real-time metrics streaming at `/api/system/ws/metrics`
- **Proxy Configuration**: Vite dev server proxies API calls to backend

## Components

### Status & Controls
- `StatusOverview`: Service status cards
- `QuickActions`: System control buttons

### Metrics
- `MetricsGrid`: Live metrics dashboard
- `AudioLevelMeter`: Voice input visualization
- `PerformanceChart`: CPU/memory/latency graphs
- `SystemResources`: Resource utilization
- `PipelineMetrics`: Voice pipeline health

### Configuration
- `ConfigPanel`: Model and system settings

### Logs
- `LogViewer`: Real-time log streaming with filters

## Development

The dashboard automatically connects to the backend via WebSocket for real-time updates. All API calls are proxied through the Vite dev server to avoid CORS issues.