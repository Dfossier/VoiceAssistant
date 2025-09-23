"""
Pipeline Performance Metrics and Instrumentation
Tracks timing for each component in the voice assistant pipeline
"""

import time
import asyncio
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
import json
from pathlib import Path
import numpy as np
from loguru import logger
from collections import deque
import threading


@dataclass
class TimingEvent:
    """Single timing event in the pipeline"""
    component: str
    operation: str
    start_time: float
    end_time: Optional[float] = None
    duration_ms: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def complete(self):
        """Mark this event as complete"""
        self.end_time = time.time()
        self.duration_ms = (self.end_time - self.start_time) * 1000


@dataclass
class PipelineTrace:
    """Complete trace of one request through the pipeline"""
    trace_id: str
    start_time: float
    end_time: Optional[float] = None
    total_duration_ms: Optional[float] = None
    events: List[TimingEvent] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_event(self, component: str, operation: str, **metadata) -> TimingEvent:
        """Add a new timing event"""
        event = TimingEvent(
            component=component,
            operation=operation,
            start_time=time.time(),
            metadata=metadata
        )
        self.events.append(event)
        return event
    
    def complete(self):
        """Mark this trace as complete"""
        self.end_time = time.time()
        self.total_duration_ms = (self.end_time - self.start_time) * 1000
        
        # Ensure all events are completed
        for event in self.events:
            if event.end_time is None:
                event.complete()
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary statistics for this trace"""
        component_times = {}
        
        for event in self.events:
            if event.duration_ms is not None:
                key = f"{event.component}.{event.operation}"
                if key not in component_times:
                    component_times[key] = []
                component_times[key].append(event.duration_ms)
        
        summary = {
            "trace_id": self.trace_id,
            "total_duration_ms": self.total_duration_ms,
            "component_breakdown": {}
        }
        
        for component, times in component_times.items():
            summary["component_breakdown"][component] = {
                "total_ms": sum(times),
                "count": len(times),
                "avg_ms": np.mean(times) if times else 0
            }
        
        return summary


class PipelineMetrics:
    """Central metrics collection for the voice assistant pipeline"""
    
    def __init__(self, max_traces: int = 100, enable_file_logging: bool = True):
        self.max_traces = max_traces
        self.enable_file_logging = enable_file_logging
        self.traces: deque[PipelineTrace] = deque(maxlen=max_traces)
        self.active_traces: Dict[str, PipelineTrace] = {}
        self.lock = threading.Lock()
        
        # Component-level metrics
        self.component_metrics: Dict[str, List[float]] = {
            "vad.inference": [],
            "vad.buffer_processing": [],
            "stt.transcription": [],
            "stt.preprocessing": [],
            "llm.generation": [],
            "llm.context_building": [],
            "tts.synthesis": [],
            "tts.postprocessing": [],
            "websocket.send": [],
            "websocket.receive": [],
            "audio.capture": [],
            "audio.playback": []
        }
        
        # Setup file logging if enabled
        if enable_file_logging:
            self.log_dir = Path("logs/metrics")
            self.log_dir.mkdir(parents=True, exist_ok=True)
            self.current_log_file = self.log_dir / f"pipeline_metrics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
    
    def start_trace(self, trace_id: str, **metadata) -> PipelineTrace:
        """Start a new pipeline trace"""
        trace = PipelineTrace(
            trace_id=trace_id,
            start_time=time.time(),
            metadata=metadata
        )
        
        with self.lock:
            self.active_traces[trace_id] = trace
        
        logger.debug(f"📊 Started trace: {trace_id}")
        return trace
    
    def get_trace(self, trace_id: str) -> Optional[PipelineTrace]:
        """Get an active trace by ID"""
        return self.active_traces.get(trace_id)
    
    def complete_trace(self, trace_id: str) -> Optional[PipelineTrace]:
        """Complete a trace and move it to history"""
        with self.lock:
            trace = self.active_traces.pop(trace_id, None)
            if trace:
                trace.complete()
                self.traces.append(trace)
                
                # Update component metrics
                for event in trace.events:
                    if event.duration_ms is not None:
                        key = f"{event.component}.{event.operation}"
                        if key in self.component_metrics:
                            self.component_metrics[key].append(event.duration_ms)
                
                # Log to file if enabled
                if self.enable_file_logging:
                    self._log_trace_to_file(trace)
                
                logger.info(f"📊 Completed trace {trace_id}: {trace.total_duration_ms:.1f}ms total")
                
        return trace
    
    def _convert_to_json_serializable(self, obj):
        """Convert numpy types and other non-serializable objects to JSON-compatible types"""
        if isinstance(obj, dict):
            return {k: self._convert_to_json_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_to_json_serializable(item) for item in obj]
        elif isinstance(obj, (np.float32, np.float64)):
            return float(obj)
        elif isinstance(obj, (np.int32, np.int64)):
            return int(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif hasattr(obj, 'item'):  # numpy scalars
            return obj.item()
        else:
            return obj

    def _log_trace_to_file(self, trace: PipelineTrace):
        """Log trace data to file"""
        try:
            trace_data = {
                "timestamp": datetime.now().isoformat(),
                "trace_id": trace.trace_id,
                "total_duration_ms": float(trace.total_duration_ms) if trace.total_duration_ms else None,
                "events": [
                    {
                        "component": e.component,
                        "operation": e.operation,
                        "duration_ms": float(e.duration_ms) if e.duration_ms else None,
                        "metadata": self._convert_to_json_serializable(e.metadata)
                    }
                    for e in trace.events
                ],
                "metadata": self._convert_to_json_serializable(trace.metadata)
            }
            
            with open(self.current_log_file, 'a') as f:
                f.write(json.dumps(trace_data) + '\n')
                
        except Exception as e:
            logger.error(f"Failed to log trace to file: {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get overall statistics across all traces"""
        stats = {
            "total_traces": len(self.traces),
            "active_traces": len(self.active_traces),
            "component_stats": {}
        }
        
        # Calculate stats for each component
        for component, times in self.component_metrics.items():
            if times:
                recent_times = times[-100:]  # Last 100 measurements
                stats["component_stats"][component] = {
                    "mean_ms": np.mean(recent_times),
                    "std_ms": np.std(recent_times),
                    "min_ms": np.min(recent_times),
                    "max_ms": np.max(recent_times),
                    "p50_ms": np.percentile(recent_times, 50),
                    "p95_ms": np.percentile(recent_times, 95),
                    "p99_ms": np.percentile(recent_times, 99),
                    "count": len(times)
                }
        
        # Calculate end-to-end latency stats
        e2e_times = [t.total_duration_ms for t in self.traces if t.total_duration_ms is not None]
        if e2e_times:
            recent_e2e = e2e_times[-100:]
            stats["end_to_end"] = {
                "mean_ms": np.mean(recent_e2e),
                "std_ms": np.std(recent_e2e),
                "min_ms": np.min(recent_e2e),
                "max_ms": np.max(recent_e2e),
                "p50_ms": np.percentile(recent_e2e, 50),
                "p95_ms": np.percentile(recent_e2e, 95),
                "p99_ms": np.percentile(recent_e2e, 99)
            }
        
        return stats
    
    def print_summary(self):
        """Print a formatted summary of current metrics"""
        stats = self.get_statistics()
        
        logger.info("\n" + "="*60)
        logger.info("📊 PIPELINE PERFORMANCE SUMMARY")
        logger.info("="*60)
        
        if "end_to_end" in stats:
            e2e = stats["end_to_end"]
            logger.info(f"\n🎯 End-to-End Latency:")
            logger.info(f"   Mean: {e2e['mean_ms']:.1f}ms")
            logger.info(f"   P50:  {e2e['p50_ms']:.1f}ms")
            logger.info(f"   P95:  {e2e['p95_ms']:.1f}ms")
            logger.info(f"   P99:  {e2e['p99_ms']:.1f}ms")
        
        logger.info(f"\n📈 Component Breakdown:")
        for component, data in stats["component_stats"].items():
            logger.info(f"\n   {component}:")
            logger.info(f"      Mean: {data['mean_ms']:.1f}ms")
            logger.info(f"      P95:  {data['p95_ms']:.1f}ms")
            logger.info(f"      Count: {data['count']}")
        
        logger.info("\n" + "="*60)
    
    def reset(self):
        """Reset all metrics"""
        with self.lock:
            self.traces.clear()
            self.active_traces.clear()
            for key in self.component_metrics:
                self.component_metrics[key].clear()
        
        logger.info("📊 Metrics reset")


# Global metrics instance
pipeline_metrics = PipelineMetrics()


# Convenience decorators for timing functions
def timed_operation(component: str, operation: str):
    """Decorator to time a function and record in metrics"""
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            # Try to get trace_id from kwargs or generate one
            trace_id = kwargs.get('trace_id', f"auto_{time.time()}")
            
            trace = pipeline_metrics.get_trace(trace_id)
            if not trace:
                trace = pipeline_metrics.start_trace(trace_id)
            
            event = trace.add_event(component, operation)
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                event.complete()
        
        def sync_wrapper(*args, **kwargs):
            # Try to get trace_id from kwargs or generate one
            trace_id = kwargs.get('trace_id', f"auto_{time.time()}")
            
            trace = pipeline_metrics.get_trace(trace_id)
            if not trace:
                trace = pipeline_metrics.start_trace(trace_id)
            
            event = trace.add_event(component, operation)
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                event.complete()
        
        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


class MetricsContext:
    """Context manager for timing operations"""
    
    def __init__(self, trace_id: str, component: str, operation: str, **metadata):
        self.trace_id = trace_id
        self.component = component
        self.operation = operation
        self.metadata = metadata
        self.event = None
        self.trace = None
    
    def __enter__(self):
        self.trace = pipeline_metrics.get_trace(self.trace_id)
        if not self.trace:
            self.trace = pipeline_metrics.start_trace(self.trace_id)
        
        self.event = self.trace.add_event(
            self.component, 
            self.operation,
            **self.metadata
        )
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.event:
            self.event.complete()
        return False
    
    async def __aenter__(self):
        return self.__enter__()
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return self.__exit__(exc_type, exc_val, exc_tb)