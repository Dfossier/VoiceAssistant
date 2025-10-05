"""
Service Coordinator - A simpler approach to fix current architecture issues
Runs multiple services in separate threads/processes without blocking
"""

import asyncio
import threading
import multiprocessing
from typing import Dict, Optional, List
from dataclasses import dataclass
from loguru import logger
import uvicorn
from fastapi import FastAPI

@dataclass
class ServiceConfig:
    name: str
    port: int
    host: str = "0.0.0.0"
    app_factory: Optional[str] = None  # e.g., "src.core.server:create_app"
    run_function: Optional[callable] = None  # For custom services
    process_type: str = "thread"  # "thread" or "process"

class ServiceCoordinator:
    """Manages multiple services without blocking each other"""
    
    def __init__(self):
        self.services: Dict[str, ServiceConfig] = {}
        self.runners: Dict[str, threading.Thread] = {}
        self.processes: Dict[str, multiprocessing.Process] = {}
        
    def register_service(self, config: ServiceConfig):
        """Register a service to be managed"""
        self.services[config.name] = config
        logger.info(f"📝 Registered service: {config.name} on port {config.port}")
        
    def start_api_service(self, config: ServiceConfig):
        """Start FastAPI service using uvicorn"""
        def run_uvicorn():
            logger.info(f"🚀 Starting {config.name} on port {config.port}")
            uvicorn.run(
                config.app_factory,
                factory=True,
                host=config.host,
                port=config.port,
                log_level="info"
            )
        
        if config.process_type == "thread":
            thread = threading.Thread(target=run_uvicorn, name=config.name)
            thread.daemon = True
            thread.start()
            self.runners[config.name] = thread
        else:
            process = multiprocessing.Process(target=run_uvicorn, name=config.name)
            process.start()
            self.processes[config.name] = process
            
    def start_voice_pipeline(self, config: ServiceConfig):
        """Start voice pipeline in separate thread"""
        def run_voice():
            logger.info(f"🎤 Starting Voice Pipeline on port {config.port}")
            import asyncio
            from src.core.enhanced_websocket_handler import EnhancedAudioWebSocketHandler
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            handler = EnhancedAudioWebSocketHandler(host=config.host, port=config.port)
            loop.run_until_complete(handler.start_server())
            
        thread = threading.Thread(target=run_voice, name=config.name)
        thread.daemon = True
        thread.start()
        self.runners[config.name] = thread
        
    def start_all(self):
        """Start all registered services"""
        logger.info("🚀 Starting all services...")
        
        for name, config in self.services.items():
            try:
                if config.app_factory:
                    self.start_api_service(config)
                elif config.run_function:
                    config.run_function(config)
                else:
                    logger.warning(f"⚠️ No start method for service: {name}")
                    
                # Small delay between service starts
                import time
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"❌ Failed to start {name}: {e}")
                
        logger.info("✅ All services started")
        
    def get_status(self) -> Dict[str, Dict]:
        """Get status of all services"""
        status = {}
        
        for name, config in self.services.items():
            is_running = False
            
            if name in self.runners:
                is_running = self.runners[name].is_alive()
            elif name in self.processes:
                is_running = self.processes[name].is_alive()
                
            status[name] = {
                "name": name,
                "port": config.port,
                "running": is_running,
                "type": config.process_type
            }
            
        return status
        
    def stop_service(self, name: str):
        """Stop a specific service"""
        if name in self.processes:
            self.processes[name].terminate()
            self.processes[name].join(timeout=5)
            del self.processes[name]
            logger.info(f"🛑 Stopped service: {name}")
            
    def wait(self):
        """Wait for all services (blocking)"""
        try:
            # Keep main thread alive
            while True:
                import time
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("⏹️ Shutting down services...")
            self.shutdown()
            
    def shutdown(self):
        """Shutdown all services"""
        for name in list(self.processes.keys()):
            self.stop_service(name)
            

# Example usage for your project
def create_coordinator():
    coordinator = ServiceCoordinator()
    
    # Register API Gateway (includes system control, metrics, etc)
    coordinator.register_service(ServiceConfig(
        name="api_gateway",
        port=8000,
        app_factory="src.core.server:create_app",
        process_type="thread"
    ))
    
    # Register Voice Pipeline separately
    coordinator.register_service(ServiceConfig(
        name="voice_pipeline", 
        port=8002,
        run_function=coordinator.start_voice_pipeline,
        process_type="thread"
    ))
    
    return coordinator
    

if __name__ == "__main__":
    # This can be your new main.py content
    from loguru import logger
    import sys
    
    logger.remove()
    logger.add(sys.stdout, level="INFO", format="{time:HH:mm:ss} | {level} | {message}")
    
    coordinator = create_coordinator()
    coordinator.start_all()
    
    # Check status
    import time
    time.sleep(3)
    status = coordinator.get_status()
    for service, info in status.items():
        logger.info(f"📊 {service}: {'🟢 Running' if info['running'] else '🔴 Stopped'} on port {info['port']}")
    
    # Keep running
    coordinator.wait()