#!/usr/bin/env python3
"""
Smart Turn VAD vs Current Buffering Approach Comparison Test
Benchmarks both approaches to evaluate improvements
"""

import asyncio
import sys
import time
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from loguru import logger

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

class CurrentBufferingVAD:
    """Replica of current buffering approach for comparison"""
    
    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate
        self.buffer = bytearray()
        self.last_activity_time = time.time()
        
    def should_process_audio(self, audio_chunk: bytes) -> bool:
        """Current buffering logic from simple_websocket_handler.py"""
        # Add to buffer
        self.buffer.extend(audio_chunk)
        buffer_size = len(self.buffer)
        
        # Calculate thresholds (from original code)
        target_size = self.sample_rate * 2 * 2  # 2 seconds of 16-bit mono
        time_since_last = time.time() - self.last_activity_time
        
        # Check for silence (simplified - in real code this analyzes amplitude)
        audio_array = np.frombuffer(audio_chunk, dtype=np.int16)
        max_amplitude = np.max(np.abs(audio_array)) if len(audio_array) > 0 else 0
        
        is_silence = max_amplitude < 100  # Simplified silence detection
        if not is_silence:
            self.last_activity_time = time.time()
            time_since_last = 0
        
        # Decision logic from original
        should_process = (
            buffer_size >= target_size or  # Buffer is full
            (buffer_size > self.sample_rate and time_since_last > 1.0)  # 1+ second silence
        )
        
        if should_process:
            self.buffer = bytearray()  # Clear buffer
            
        return should_process
    
    def get_detection_delay(self) -> float:
        """Calculate expected detection delay"""
        buffer_size = len(self.buffer)
        # Time to fill buffer or wait for silence
        buffer_delay = max(0, (self.sample_rate * 2 * 2 - buffer_size) / (self.sample_rate * 2))
        silence_delay = 1.0  # 1 second silence requirement
        return min(buffer_delay, silence_delay)

class SmartTurnVADWrapper:
    """Wrapper for Smart Turn VAD for comparison"""
    
    def __init__(self):
        self.analyzer = None
        self.initialization_error = None
        
    async def initialize(self) -> bool:
        """Initialize Smart Turn analyzer"""
        try:
            from pipecat.analyzers.smart_turn import LocalSmartTurnAnalyzerV3
            self.analyzer = LocalSmartTurnAnalyzerV3()
            logger.info("✅ Smart Turn VAD initialized")
            return True
        except Exception as e:
            self.initialization_error = str(e)
            logger.error(f"❌ Smart Turn initialization failed: {e}")
            return False
    
    async def detect_turn_end(self, audio_data: bytes) -> Tuple[bool, float]:
        """Detect turn end and return (is_turn_end, confidence)"""
        if not self.analyzer:
            return False, 0.0
        
        try:
            start_time = time.time()
            result = await self.analyzer.analyze(audio_data)
            inference_time = (time.time() - start_time) * 1000  # ms
            
            # Extract turn detection result (format depends on implementation)
            is_turn_end = bool(result) if result is not None else False
            confidence = getattr(result, 'confidence', 1.0) if hasattr(result, 'confidence') else 1.0
            
            return is_turn_end, confidence, inference_time
            
        except Exception as e:
            logger.error(f"❌ Smart Turn detection error: {e}")
            return False, 0.0, 0.0

def create_conversation_scenarios() -> List[Tuple[str, bytes, float]]:
    """Create various conversation test scenarios"""
    scenarios = []
    sample_rate = 16000
    
    # Scenario 1: Short question (should trigger quickly)
    logger.info("🎵 Creating scenario 1: Short question")
    duration = 1.5  # 1.5 seconds of speech
    samples = int(sample_rate * duration)
    t = np.linspace(0, duration, samples)
    audio = np.sin(2 * np.pi * 200 * t) * 0.3  # Speech-like tone
    audio += np.random.normal(0, 0.05, samples)  # Add noise
    # Add 0.5s silence at end
    silence_samples = int(0.5 * sample_rate)
    audio = np.concatenate([audio, np.zeros(silence_samples)])
    audio_bytes = (audio * 32767).clip(-32768, 32767).astype(np.int16).tobytes()
    scenarios.append(("Short question", audio_bytes, 2.0))  # Expected ~2s total
    
    # Scenario 2: Long statement (should wait for natural end)
    logger.info("🎵 Creating scenario 2: Long statement")  
    duration = 4.0  # 4 seconds of speech
    samples = int(sample_rate * duration)
    t = np.linspace(0, duration, samples)
    # More complex speech pattern with pauses
    speech = np.sin(2 * np.pi * 180 * t) * 0.3
    speech *= (1 + 0.5 * np.sin(2 * np.pi * 0.5 * t))  # Amplitude modulation
    speech += np.random.normal(0, 0.03, samples)
    # Add brief pause in middle
    mid_pause_start = int(2 * sample_rate)
    mid_pause_end = int(2.3 * sample_rate)
    speech[mid_pause_start:mid_pause_end] *= 0.1  # Quiet but not silent
    # Add final silence
    silence_samples = int(0.8 * sample_rate)
    speech = np.concatenate([speech, np.zeros(silence_samples)])
    audio_bytes = (speech * 32767).clip(-32768, 32767).astype(np.int16).tobytes()
    scenarios.append(("Long statement with pause", audio_bytes, 4.8))
    
    # Scenario 3: Hesitation pattern (um, uh, thinking)
    logger.info("🎵 Creating scenario 3: Hesitation pattern")
    duration = 2.5
    samples = int(sample_rate * duration)
    t = np.linspace(0, duration, samples)
    
    # Create hesitation pattern: speech - pause - "um" - pause - speech
    speech = np.zeros(samples)
    # Initial speech (0-0.8s)
    speech_part1 = np.sin(2 * np.pi * 190 * t[:int(0.8*sample_rate)]) * 0.3
    speech[:int(0.8*sample_rate)] = speech_part1
    # Pause (0.8-1.0s) - very quiet
    # "Um" sound (1.0-1.2s)
    um_samples = int(0.2 * sample_rate)
    um_start = int(1.0 * sample_rate)
    speech[um_start:um_start+um_samples] = np.sin(2 * np.pi * 120 * t[um_start:um_start+um_samples]) * 0.2
    # Another pause (1.2-1.5s)
    # Final speech (1.5-2.5s)  
    final_start = int(1.5 * sample_rate)
    speech[final_start:] = np.sin(2 * np.pi * 200 * t[final_start:]) * 0.3
    
    speech += np.random.normal(0, 0.04, samples)
    # Add silence
    silence_samples = int(1.0 * sample_rate)
    speech = np.concatenate([speech, np.zeros(silence_samples)])
    audio_bytes = (speech * 32767).clip(-32768, 32767).astype(np.int16).tobytes()
    scenarios.append(("Hesitation with um/uh", audio_bytes, 3.5))
    
    logger.info(f"✅ Created {len(scenarios)} conversation scenarios")
    return scenarios

async def test_scenario(
    scenario_name: str, 
    audio_data: bytes, 
    expected_duration: float,
    current_vad: CurrentBufferingVAD,
    smart_turn: SmartTurnVADWrapper
) -> Dict:
    """Test both VAD approaches on a scenario"""
    logger.info(f"\n🎯 Testing scenario: {scenario_name}")
    results = {
        'scenario': scenario_name,
        'expected_duration': expected_duration,
        'current_approach': {},
        'smart_turn_approach': {}
    }
    
    # Test current buffering approach
    logger.info("   📊 Testing current buffering approach...")
    start_time = time.time()
    
    # Simulate processing audio in chunks
    chunk_size = 8000  # 500ms chunks (16000 Hz * 0.5s * 2 bytes/sample)
    current_detected = False
    current_detection_time = 0
    
    for i in range(0, len(audio_data), chunk_size):
        chunk = audio_data[i:i+chunk_size]
        if current_vad.should_process_audio(chunk):
            current_detection_time = time.time() - start_time
            current_detected = True
            break
    
    if not current_detected:
        current_detection_time = expected_duration + 2.0  # Max buffer time
    
    results['current_approach'] = {
        'detected': current_detected,
        'detection_time': current_detection_time,
        'method': 'buffering'
    }
    
    # Test Smart Turn approach
    logger.info("   🤖 Testing Smart Turn approach...")
    if smart_turn.analyzer:
        start_time = time.time()
        is_turn_end, confidence, inference_time = await smart_turn.detect_turn_end(audio_data)
        detection_time = inference_time / 1000.0  # Convert ms to seconds
        
        results['smart_turn_approach'] = {
            'detected': is_turn_end,
            'confidence': confidence,
            'detection_time': detection_time,
            'inference_time_ms': inference_time,
            'method': 'semantic'
        }
    else:
        results['smart_turn_approach'] = {
            'detected': False,
            'error': smart_turn.initialization_error,
            'method': 'semantic'
        }
    
    # Log comparison
    logger.info(f"   📊 Results for '{scenario_name}':")
    logger.info(f"      Current: {current_detection_time:.3f}s")
    if 'inference_time_ms' in results['smart_turn_approach']:
        smart_time = results['smart_turn_approach']['inference_time_ms']
        logger.info(f"      Smart Turn: {smart_time:.1f}ms")
        improvement = (current_detection_time * 1000 - smart_time)
        logger.info(f"      Improvement: {improvement:.0f}ms faster" if improvement > 0 else f"      Difference: {abs(improvement):.0f}ms slower")
    
    return results

async def run_comparison_tests():
    """Run comprehensive comparison tests"""
    logger.info("🎯 Smart Turn VAD vs Current Buffering Comparison")
    logger.info("=" * 60)
    
    # Initialize both approaches
    current_vad = CurrentBufferingVAD()
    smart_turn = SmartTurnVADWrapper()
    
    logger.info("🔧 Initializing VAD approaches...")
    smart_turn_available = await smart_turn.initialize()
    
    if not smart_turn_available:
        logger.warning("⚠️ Smart Turn not available - testing current approach only")
    
    # Create test scenarios
    scenarios = create_conversation_scenarios()
    
    # Run tests
    all_results = []
    for scenario_name, audio_data, expected_duration in scenarios:
        results = await test_scenario(
            scenario_name, audio_data, expected_duration,
            current_vad, smart_turn
        )
        all_results.append(results)
        
        # Reset current VAD for next test
        current_vad = CurrentBufferingVAD()
    
    # Generate summary report
    logger.info("\n📊 COMPARISON SUMMARY")
    logger.info("=" * 60)
    
    if smart_turn_available:
        current_times = [r['current_approach']['detection_time'] for r in all_results]
        smart_times = [r['smart_turn_approach'].get('inference_time_ms', 0)/1000.0 for r in all_results]
        
        avg_current = np.mean(current_times) * 1000  # Convert to ms
        avg_smart = np.mean(smart_times) * 1000
        
        logger.info(f"📈 Average Detection Times:")
        logger.info(f"   Current Buffering: {avg_current:.0f}ms")
        logger.info(f"   Smart Turn VAD:   {avg_smart:.1f}ms")
        logger.info(f"   Average Improvement: {avg_current - avg_smart:.0f}ms")
        
        # Performance analysis
        if avg_smart < 10:
            logger.info("🚀 Smart Turn: Excellent GPU-level performance!")
        elif avg_smart < 60:
            logger.info("✅ Smart Turn: Good CPU-level performance")
        else:
            logger.warning("⚠️ Smart Turn: Slower than expected")
        
        improvement_percent = ((avg_current - avg_smart) / avg_current) * 100
        logger.info(f"📊 Speed Improvement: {improvement_percent:.1f}%")
        
    else:
        logger.info("❌ Smart Turn comparison not available")
        logger.info("💡 Install Smart Turn: pip install 'pipecat-ai[local-smart-turn-v3]==0.0.85'")
    
    logger.info("\n🔧 Next Steps:")
    logger.info("   1. If Smart Turn shows good performance, proceed with integration")
    logger.info("   2. Test with real Discord voice conversations") 
    logger.info("   3. Implement feature flag for gradual rollout")
    
    return all_results

async def main():
    """Main test function"""
    try:
        results = await run_comparison_tests()
        logger.info("✅ Comparison testing completed successfully")
        return results
    except KeyboardInterrupt:
        logger.info("⏹️ Testing interrupted by user")
    except Exception as e:
        logger.error(f"❌ Testing failed with error: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())