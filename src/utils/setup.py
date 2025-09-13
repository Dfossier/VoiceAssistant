"""Setup and environment checking utilities"""
import os
import sys
import subprocess
from pathlib import Path
from typing import List, Tuple, Dict

from loguru import logger


def check_environment() -> bool:
    """Check if the environment is properly set up"""
    checks_passed = True
    
    # Check Python version
    python_version = sys.version_info
    if python_version.major < 3 or (python_version.major == 3 and python_version.minor < 11):
        logger.error(f"Python 3.11+ required, found {python_version.major}.{python_version.minor}")
        checks_passed = False
    else:
        logger.info(f"Python version: {python_version.major}.{python_version.minor} ✓")
    
    # Check for .env file
    env_path = Path(".env")
    if not env_path.exists():
        logger.warning(".env file not found. Please copy .env.example and configure.")
        checks_passed = False
    else:
        logger.info(".env file found ✓")
    
    # Check WSL environment
    if os.path.exists("/proc/version"):
        with open("/proc/version", "r") as f:
            if "microsoft" in f.read().lower():
                logger.info("Running in WSL ✓")
            else:
                logger.info("Running in Linux (not WSL)")
    
    # Check for required system commands
    required_commands = ["git", "python3", "pip"]
    for cmd in required_commands:
        if check_command_exists(cmd):
            logger.info(f"Command '{cmd}' found ✓")
        else:
            logger.error(f"Command '{cmd}' not found")
            checks_passed = False
    
    return checks_passed


def check_command_exists(command: str) -> bool:
    """Check if a command exists in the system PATH"""
    try:
        subprocess.run(
            ["which", command],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True
        )
        return True
    except subprocess.CalledProcessError:
        return False


def setup_directories():
    """Create necessary directories if they don't exist"""
    directories = [
        "logs",
        "static/js",
        "static/css",
        "static/images",
        "data",
        "cache",
        "temp"
    ]
    
    for directory in directories:
        path = Path(directory)
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created directory: {directory}")


def get_windows_path(wsl_path: str) -> str:
    """Convert WSL path to Windows path"""
    if wsl_path.startswith("/mnt/"):
        # Extract drive letter and path
        parts = wsl_path[5:].split("/", 1)
        if len(parts) == 2:
            drive_letter = parts[0].upper()
            path = parts[1].replace("/", "\\")
            return f"{drive_letter}:\\{path}"
    return wsl_path


def get_wsl_path(windows_path: str) -> str:
    """Convert Windows path to WSL path"""
    if len(windows_path) >= 3 and windows_path[1] == ":" and windows_path[2] == "\\":
        drive_letter = windows_path[0].lower()
        path = windows_path[3:].replace("\\", "/")
        return f"/mnt/{drive_letter}/{path}"
    return windows_path


def check_port_available(port: int) -> bool:
    """Check if a port is available for use"""
    import socket
    
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("", port))
            return True
    except OSError:
        return False


def get_system_info() -> Dict[str, str]:
    """Get system information"""
    info = {
        "platform": sys.platform,
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "executable": sys.executable
    }
    
    # Get WSL info if available
    if os.path.exists("/proc/version"):
        with open("/proc/version", "r") as f:
            version_info = f.read().strip()
            if "microsoft" in version_info.lower():
                info["wsl_version"] = "WSL2" if "WSL2" in version_info else "WSL1"
    
    # Get Windows info if in WSL
    if "wsl_version" in info:
        try:
            result = subprocess.run(
                ["cmd.exe", "/c", "ver"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                info["windows_version"] = result.stdout.strip()
        except:
            pass
    
    return info


def install_playwright_browsers():
    """Install Playwright browsers if not already installed"""
    try:
        logger.info("Checking Playwright browsers...")
        result = subprocess.run(
            ["playwright", "install", "chromium"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            logger.info("Playwright browsers installed ✓")
        else:
            logger.error(f"Failed to install Playwright browsers: {result.stderr}")
    except Exception as e:
        logger.error(f"Error installing Playwright browsers: {e}")