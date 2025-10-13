import psutil
import os
import sys

def find_discord_bot():
    """Find Discord bot processes"""
    print("Searching for Discord bot processes...\n")
    
    discord_processes = []
    python_processes = []
    
    # Iterate through all processes
    for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
        try:
            # Check if it's a Python process
            if proc.info['name'] and 'python' in proc.info['name'].lower():
                python_processes.append(proc)
                
                # Check command line for Discord bot indicators
                if proc.info['cmdline']:
                    cmdline = ' '.join(proc.info['cmdline']).lower()
                    if any(keyword in cmdline for keyword in ['discord', 'bot.py', 'discordbot']):
                        discord_processes.append(proc)
                        
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    
    # Display results
    if discord_processes:
        print("=== LIKELY DISCORD BOT PROCESSES ===")
        for proc in discord_processes:
            try:
                print(f"PID: {proc.pid}")
                print(f"Name: {proc.name()}")
                print(f"Command: {' '.join(proc.cmdline())}")
                print(f"Status: {proc.status()}")
                print(f"Created: {proc.create_time()}")
                
                # Check if process is using network
                connections = proc.connections()
                if connections:
                    print("Network connections:")
                    for conn in connections:
                        print(f"  - {conn.laddr} -> {conn.raddr if conn.raddr else 'N/A'}")
                print("-" * 50)
            except:
                pass
    else:
        print("No obvious Discord bot processes found.\n")
    
    print("\n=== ALL PYTHON PROCESSES ===")
    for proc in python_processes:
        try:
            print(f"PID: {proc.pid} - {proc.name()}")
            if proc.cmdline():
                print(f"  Command: {' '.join(proc.cmdline()[:3])}...")  # First 3 args
        except:
            pass
    
    # Check for processes using port 8000 (backend API)
    print("\n=== PROCESSES USING PORT 8000 ===")
    for conn in psutil.net_connections():
        if conn.laddr.port == 8000 and conn.pid:
            try:
                proc = psutil.Process(conn.pid)
                print(f"PID: {conn.pid} - {proc.name()}")
            except:
                pass
    
    return discord_processes, python_processes

def kill_process(pid):
    """Kill a process by PID"""
    try:
        proc = psutil.Process(pid)
        proc.terminate()
        proc.wait(timeout=5)  # Wait up to 5 seconds
        print(f"Process {pid} terminated.")
    except psutil.TimeoutExpired:
        proc.kill()  # Force kill if terminate didn't work
        print(f"Process {pid} force killed.")
    except Exception as e:
        print(f"Error killing process {pid}: {e}")

if __name__ == "__main__":
    # Check if psutil is installed
    try:
        import psutil
    except ImportError:
        print("Installing psutil...")
        os.system(f"{sys.executable} -m pip install psutil")
        import psutil
    
    discord_procs, python_procs = find_discord_bot()
    
    print("\n" + "="*50)
    choice = input("\nDo you want to kill processes? (y/n): ")
    
    if choice.lower() == 'y':
        if discord_procs:
            print("\nKill Discord bot processes:")
            for i, proc in enumerate(discord_procs):
                print(f"{i+1}. PID {proc.pid} - {proc.name()}")
            
            selection = input("Enter number to kill, 'all' for all, or 'skip': ")
            if selection == 'all':
                for proc in discord_procs:
                    kill_process(proc.pid)
            elif selection.isdigit():
                idx = int(selection) - 1
                if 0 <= idx < len(discord_procs):
                    kill_process(discord_procs[idx].pid)
        
        if not discord_procs or input("\nKill all Python processes? (y/n): ").lower() == 'y':
            print("\nKilling all Python processes...")
            for proc in python_processes:
                try:
                    kill_process(proc.pid)
                except:
                    pass
            print("All Python processes killed!")