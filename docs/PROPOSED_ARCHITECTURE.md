# Proposed Architecture: Modular Voice Assistant System

## Overview
A microservices-inspired architecture that separates concerns, improves reliability, and enables independent scaling of components.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Web Dashboard (React)                         │
│                          Port: 3000                                  │
│  ┌──────────────┬──────────────┬──────────────┬─────────────────┐  │
│  │   Monitor    │   Control    │    Config    │      Logs       │  │
│  └──────────────┴──────────────┴──────────────┴─────────────────┘  │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ HTTP/WebSocket
┌───────────────────────────────▼─────────────────────────────────────┐
│                      API Gateway / Orchestrator                      │
│                          Port: 8000                                  │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  • Service Discovery & Health Checks                            │ │
│  │  • Request Routing & Load Balancing                             │ │
│  │  • Authentication & Rate Limiting                               │ │
│  │  • WebSocket Proxy & Connection Management                      │ │
│  └────────────────────────────────────────────────────────────────┘ │
└──────┬──────────┬──────────┬──────────┬──────────┬─────────────────┘
       │          │          │          │          │
       │          │          │          │          │ IPC/Redis
┌──────▼────┐ ┌──▼────┐ ┌──▼────┐ ┌──▼────┐ ┌──▼────┐
│  Voice    │ │System │ │ LLM   │ │ File  │ │Metrics│
│ Pipeline  │ │Control│ │Service│ │Monitor│ │Collect│
│  :8001    │ │ :8002 │ │ :8003 │ │ :8004 │ │ :8005 │
└───────────┘ └───────┘ └───────┘ └───────┘ └───────┘
       │                     │         │          │
       └─────────┬───────────┴─────────┴──────────┘
                 │ Message Queue (Redis Pub/Sub)
      ┌──────────▼────────────────────────┐
      │     Discord Bot (Windows)         │
      │  • Direct Audio Capture           │
      │  • WebSocket Client to Pipeline   │
      │  • Command Processing             │
      └───────────────────────────────────┘
```

## Core Components

### 1. **API Gateway / Orchestrator** (Port 8000)
```python
# src/services/api_gateway/main.py
"""
Central orchestrator that manages all services
- FastAPI-based API Gateway
- Service registry and health monitoring
- Request routing to appropriate services
- WebSocket connection management
- Unified logging and metrics collection
"""
```

**Key Features:**
- Service discovery and registration
- Health check endpoints for all services
- Intelligent request routing
- WebSocket multiplexing
- Circuit breaker pattern for resilience

### 2. **Voice Pipeline Service** (Port 8001)
```python
# src/services/voice_pipeline/main.py
"""
Dedicated voice processing service
- Whisper STT
- Phi-3 LLM integration
- Kokoro TTS
- Smart Turn VAD
- Audio streaming via WebSocket
"""
```

**Isolation Benefits:**
- Can restart without affecting other services
- Resource allocation specifically for ML models
- Independent scaling based on voice load

### 3. **System Control Service** (Port 8002)
```python
# src/services/system_control/main.py
"""
Service lifecycle management
- Start/stop/restart services
- Process monitoring
- Resource usage tracking
- Log aggregation
"""
```

### 4. **LLM Service** (Port 8003)
```python
# src/services/llm/main.py
"""
Dedicated LLM processing
- Multiple model support (OpenAI, Anthropic, Local)
- Context management
- Claude Code integration
- Conversation history
"""
```

### 5. **File Monitor Service** (Port 8004)
```python
# src/services/file_monitor/main.py
"""
File system monitoring
- Watch directories for changes
- Code analysis
- Project context extraction
"""
```

### 6. **Metrics Collector** (Port 8005)
```python
# src/services/metrics/main.py
"""
System-wide metrics collection
- Performance metrics
- Resource usage
- Service health
- Real-time dashboard data
"""
```

## Communication Patterns

### 1. **Inter-Service Communication**
```python
# Using Redis for pub/sub and caching
REDIS_CONFIG = {
    'host': 'localhost',
    'port': 6379,
    'decode_responses': True
}

# Event-driven architecture
EVENTS = {
    'voice.transcription.complete': 'Voice -> LLM',
    'llm.response.ready': 'LLM -> Voice',
    'system.service.status': 'Control -> Gateway',
    'metrics.update': 'All -> Metrics'
}
```

### 2. **Service Discovery**
```python
# services/common/discovery.py
class ServiceRegistry:
    def register(self, name: str, host: str, port: int, health_endpoint: str):
        """Register service with gateway"""
        
    def discover(self, service_name: str) -> ServiceInfo:
        """Get service connection info"""
        
    def health_check_all(self) -> Dict[str, HealthStatus]:
        """Check all services health"""
```

## Implementation Benefits

### 1. **Reliability**
- Services can fail independently
- Automatic restart of failed services
- No single point of failure
- Circuit breakers prevent cascade failures

### 2. **Scalability**
- Each service can be scaled independently
- Voice pipeline can use GPU while others use CPU
- Horizontal scaling possible for stateless services

### 3. **Development**
- Teams can work on services independently
- Clear API contracts between services
- Easier testing of individual components
- Hot reload without affecting other services

### 4. **Monitoring**
- Per-service metrics and logs
- Distributed tracing for request flow
- Easy to identify bottlenecks
- Real-time performance dashboards

## Migration Path

### Phase 1: Extract Core Services
```bash
# Create service structure
mkdir -p src/services/{gateway,voice,control,llm,monitor,metrics}

# Move existing code to services
mv src/core/enhanced_websocket_handler.py src/services/voice/
mv src/api/system_control.py src/services/control/
```

### Phase 2: Implement Service Registry
```python
# Basic service registry with health checks
from fastapi import FastAPI
from typing import Dict, Optional
import httpx
import asyncio

class ServiceRegistry:
    def __init__(self):
        self.services: Dict[str, ServiceInfo] = {}
        
    async def register_service(self, name: str, url: str, health_path: str = "/health"):
        self.services[name] = ServiceInfo(url=url, health_path=health_path)
        
    async def check_health(self, service_name: str) -> bool:
        service = self.services.get(service_name)
        if not service:
            return False
            
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{service.url}{service.health_path}")
                return response.status_code == 200
        except:
            return False
```

### Phase 3: Docker Compose Setup
```yaml
# docker-compose.yml
version: '3.8'

services:
  redis:
    image: redis:alpine
    ports:
      - "6379:6379"
      
  api-gateway:
    build: ./src/services/gateway
    ports:
      - "8000:8000"
    depends_on:
      - redis
    environment:
      - REDIS_URL=redis://redis:6379
      
  voice-pipeline:
    build: ./src/services/voice
    ports:
      - "8001:8001"
    depends_on:
      - redis
    volumes:
      - ./models:/models
    deploy:
      resources:
        reservations:
          devices:
            - capabilities: [gpu]
              
  system-control:
    build: ./src/services/control
    ports:
      - "8002:8002"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      
  # ... other services
```

## Configuration Management

### Centralized Config
```yaml
# config/services.yml
services:
  voice_pipeline:
    host: localhost
    port: 8001
    models:
      whisper: "small"
      llm: "phi-3-mini"
      tts: "kokoro"
    
  system_control:
    host: localhost
    port: 8002
    
  api_gateway:
    host: 0.0.0.0
    port: 8000
    cors_origins:
      - http://localhost:3000
```

## Web Dashboard Updates

### Service Status Grid
```typescript
// components/ServiceGrid.tsx
interface Service {
  name: string
  status: 'running' | 'stopped' | 'error'
  port: number
  health: {
    cpu: number
    memory: number
    uptime: number
    lastCheck: Date
  }
}

export const ServiceGrid: React.FC = () => {
  const services = useServiceStatus()
  
  return (
    <div className="grid grid-cols-3 gap-4">
      {services.map(service => (
        <ServiceCard key={service.name} service={service} />
      ))}
    </div>
  )
}
```

## Next Steps

1. **Start Simple**: Begin by separating voice pipeline from API
2. **Add Redis**: For inter-service communication
3. **Implement Gateway**: Basic routing and health checks
4. **Migrate Services**: One at a time
5. **Add Monitoring**: Prometheus + Grafana
6. **Container Setup**: Docker for easy deployment

This architecture provides:
- ✅ **Clear separation of concerns**
- ✅ **Independent service scaling**
- ✅ **Better fault isolation**
- ✅ **Easier debugging and monitoring**
- ✅ **Professional production-ready structure**

Would you like me to start implementing this architecture, beginning with extracting the voice pipeline into its own service?