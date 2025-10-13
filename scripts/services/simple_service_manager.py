"""
Simple Service Manager - Fixed version without GUI complexity
Manages both WSL Backend and Windows Discord Bot
"""
import subprocess
import psutil
import time
import logging
import requests
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SimpleServiceManager:
    """Simple service manager without GUI"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.processes = {}
        
    def is_backend_running(self):
        """Check if backend is running"""
        try:
            response = requests.get("http://localhost:8000/health", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def start_wsl_backend(self):
        """Start WSL backend"""
        if self.is_backend_running():
            logger.info("Backend already running")
            return True
            
        try:
            logger.info("Starting WSL Backend...")
            cmd = [
                "wsl", "-d", "Ubuntu", "bash", "-c", 
                "cd /mnt/c/users/dfoss/desktop/localaimodels/assistant && python3 main.py"
            ]
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
            )
            
            self.processes['wsl_backend'] = process
            
            # Wait a moment and check
            time.sleep(3)
            if self.is_backend_running():
                logger.info("✅ WSL Backend started successfully")
                return True
            else:
                logger.error("❌ WSL Backend failed to start")
                return False
                
        except Exception as e:
            logger.error(f"Error starting WSL backend: {e}")
            return False
    
    def start_discord_bot(self):
        """Start Windows Discord Bot"""
        try:
            bot_dir = self.project_root / "WindowsDiscordBot"
            venv_python = bot_dir / "venv" / "Scripts" / "python.exe"
            
            if not venv_python.exists():
                logger.error("❌ Virtual environment not found. Run setup_windows.bat first")
                return False
            
            logger.info("Starting Windows Discord Bot...")
            
            process = subprocess.Popen(
                [str(venv_python), "bot.py"],
                cwd=str(bot_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
            )
            
            self.processes['discord_bot'] = process
            
            # Give it a moment
            time.sleep(2)
            if process.poll() is None:
                logger.info("✅ Discord Bot started successfully")
                return True
            else:
                logger.error("❌ Discord Bot failed to start")
                return False
                
        except Exception as e:
            logger.error(f"Error starting Discord bot: {e}")
            return False
    
    def stop_service(self, service_name):
        """Stop a service"""
        if service_name == 'wsl_backend':
            try:
                subprocess.run([
                    "wsl", "-d", "Ubuntu", "bash", "-c",
                    "pkill -f 'python3.*main.py' || true"
                ], check=True)
                logger.info("✅ WSL Backend stopped")
                return True
            except Exception as e:
                logger.error(f"Error stopping WSL backend: {e}")
                return False
                
        elif service_name == 'discord_bot':
            process = self.processes.get('discord_bot')
            if process and process.poll() is None:
                try:
                    process.terminate()
                    process.wait(timeout=10)
                    logger.info("✅ Discord Bot stopped")
                    return True
                except subprocess.TimeoutExpired:
                    process.kill()
                    logger.info("✅ Discord Bot force killed")
                    return True
                except Exception as e:
                    logger.error(f"Error stopping Discord bot: {e}")
                    return False
            else:
                logger.info("Discord Bot not running")
                return True
    
    def get_status(self):
        """Get status of both services"""
        status = {}
        
        # Backend status
        status['backend'] = {
            'running': self.is_backend_running(),
            'url': 'http://localhost:8000'
        }
        
        # Discord bot status
        process = self.processes.get('discord_bot')
        status['discord_bot'] = {
            'running': process and process.poll() is None,
            'process_id': process.pid if process and process.poll() is None else None
        }
        
        return status
    
    def print_status(self):
        """Print current status"""
        status = self.get_status()
        
        print("=== AI Assistant Service Status ===")
        print()
        
        backend_icon = "✅" if status['backend']['running'] else "❌"
        print(f"{backend_icon} WSL Backend API: {'Running' if status['backend']['running'] else 'Stopped'}")
        if status['backend']['running']:
            print(f"   URL: {status['backend']['url']}")
        
        bot_icon = "✅" if status['discord_bot']['running'] else "❌"
        print(f"{bot_icon} Discord Bot: {'Running' if status['discord_bot']['running'] else 'Stopped'}")
        if status['discord_bot']['process_id']:
            print(f"   PID: {status['discord_bot']['process_id']}")
        
        print()

def main():
    """Main CLI interface"""
    manager = SimpleServiceManager()
    
    print("Simple AI Assistant Service Manager")
    print("==================================")
    print()
    
    while True:
        manager.print_status()
        
        print("Commands:")
        print("  1 - Start WSL Backend")
        print("  2 - Start Discord Bot") 
        print("  3 - Start Both")
        print("  4 - Stop WSL Backend")
        print("  5 - Stop Discord Bot")
        print("  6 - Stop Both")
        print("  7 - Refresh Status")
        print("  0 - Exit")
        print()
        
        try:
            choice = input("Enter command: ").strip()
            
            if choice == "1":
                manager.start_wsl_backend()
            elif choice == "2":
                manager.start_discord_bot()
            elif choice == "3":
                manager.start_wsl_backend()
                time.sleep(2)
                manager.start_discord_bot()
            elif choice == "4":
                manager.stop_service('wsl_backend')
            elif choice == "5":
                manager.stop_service('discord_bot')
            elif choice == "6":
                manager.stop_service('wsl_backend')
                manager.stop_service('discord_bot')
            elif choice == "7":
                continue  # Just refresh
            elif choice == "0":
                print("Stopping all services before exit...")
                manager.stop_service('wsl_backend')
                manager.stop_service('discord_bot')
                break
            else:
                print("Invalid choice")
            
            print()
            time.sleep(1)
            
        except KeyboardInterrupt:
            print("\nStopping all services...")
            manager.stop_service('wsl_backend')
            manager.stop_service('discord_bot')
            break
        except Exception as e:
            logger.error(f"Error: {e}")
            time.sleep(1)

if __name__ == "__main__":
    main()