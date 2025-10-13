# Kokoro TTS / Phonemizer Issue Analysis

## Root Cause

The issue is a version incompatibility between:
- **Kokoro 0.9.2** (via its dependency **misaki 0.9.4**)
- **phonemizer 3.3.0**

The problem occurs in `/venv/lib/python3.12/site-packages/misaki/espeak.py` line 10:
```python
EspeakWrapper.set_data_path(espeakng_loader.get_data_path())
```

The `EspeakWrapper` class in phonemizer 3.3.0 does NOT have a `set_data_path()` method. It only has:
- `data_path` as a property
- `set_library()` method
- But NO `set_data_path()` method

## Current Workarounds in the Codebase

1. **fix_kokoro_phonemizer.py** - A monkey patch that adds the missing method
2. **kokoro_wrapper.py** - A simplified wrapper that bypasses phonemizer entirely
3. **kokoro_direct.py** - Direct model loading without using the official Kokoro pipeline

## Are We Using the Real Kokoro Model?

Based on my analysis:

1. **YES**, the model files are present:
   - `/mnt/c/users/dfoss/desktop/localaimodels/kokoro-tts/kokoro-v1_0.pth` (312.1 MB)
   - This is the official Kokoro v1.0 model checkpoint

2. **PARTIALLY**, the implementations vary:
   - `kokoro_tts_service.py` - Tries to use the official KPipeline (but fails without the fix)
   - `kokoro_wrapper.py` - Falls back to Windows TTS when Kokoro fails
   - `kokoro_direct.py` - Attempts direct model usage but is incomplete

3. **The Fix Works**: The monkey patch in `fix_kokoro_phonemizer.py` successfully allows importing Kokoro

## Solution

The phonemizer compatibility has been fixed by:
1. Adding a monkey patch that creates the missing `set_data_path` method
2. Applied the patch in `kokoro_tts_service.py` before importing Kokoro

## Recommendations

1. **Use the patched kokoro_tts_service.py** - This now includes the fix and should work with the real Kokoro model
2. **Alternative**: Use an older version of phonemizer that has the `set_data_path` method
3. **Long-term**: Wait for Kokoro/misaki to update for phonemizer 3.3.0 compatibility

## Testing the Fix

To verify Kokoro is working:
```python
# This should now work:
from fix_kokoro_phonemizer import patch_espeak_wrapper
patch_espeak_wrapper()
from kokoro import KPipeline

# Create pipeline
pipeline = KPipeline(lang_code='a', model_dir='/mnt/c/users/dfoss/desktop/localaimodels/kokoro-tts')
```

The actual Kokoro model IS being used when the service successfully initializes.