# WSL2 Mirrored Networking Setup

## 🎯 Problem Solved

WSL2 Mirrored Networking Mode eliminates connectivity issues between Windows applications (like Discord bots) and WSL2 services (like the AI assistant backend).

## ✅ Benefits

- **No firewall changes** - Uses Windows' built-in networking
- **No port forwarding** - Direct localhost access
- **Bidirectional** - Windows ↔ WSL communication works both ways
- **Secure** - No external port exposure
- **Automatic** - Works with Windows updates

## 🔧 Setup Instructions

### 1. Enable Mirrored Networking (One-time setup)

Run this PowerShell script **as Administrator**:

```powershell
# enable_mirrored_networking.ps1
.\enable_mirrored_networking.ps1
```

This creates/updates `C:\Users\<username>\.wslconfig`:

```ini
[wsl2]
networkingMode=mirrored
dnsTunneling=true
firewall=true
autoProxy=true
```

### 2. Restart WSL

```bash
# From WSL
wsl --shutdown
wsl  # Restart WSL
```

### 3. Test Connectivity

```bash
./test_networking.sh
```

Expected output:
```
✅ Backend accessible from WSL
✅ WebSocket connection successful!
✅ Mirrored networking is working!
✅ Discord bot should now connect successfully
```

## 🔄 How It Works

Before Mirrored Networking:
```
Windows Discord Bot → ❌ Can't reach WSL (172.20.104.13:8000)
WSL Backend → ❌ Can't reach Windows services
```

After Mirrored Networking:
```
Windows Discord Bot → ✅ localhost:8000 → WSL Backend
WSL Backend → ✅ localhost:* → Windows services
```

## 📋 Configuration

The Discord bot is now configured to connect to:
- **Before:** `ws://172.20.104.13:8000` (WSL IP - unreliable)
- **After:** `ws://127.0.0.1:8000` (localhost - reliable)

## 🐛 Troubleshooting

### Test fails after setup:
```bash
# Restart WSL completely
wsl --shutdown
wsl --update
wsl
```

### Still not working:
```bash
# Check WSL version
wsl --version

# Should show: WSL version: 2.0.4+ (or higher)
```

### Windows version check:
```powershell
# Run in PowerShell
Get-ComputerInfo | Select-Object WindowsProductName, WindowsVersion
# Should show: Windows 11 22H2+ (build 22621+)
```

## 🎉 Result

Once enabled, the Discord bot connects seamlessly to the WSL backend using standard localhost addressing. No more network configuration headaches!

**This is the recommended long-term solution for Windows-WSL development.** 🚀
