import os
import multiprocessing
import psutil
from pathlib import Path

def generate_systemd():
    """Generates a hardened systemd unit file for the RouteMaster V3 Gateway."""
    user = "root" # Standard for unmanaged VPS, though 'www-data' is better if setup
    working_dir = str(Path(__file__).parent.parent.absolute())
    
    # Calculate recommended memory limit (85% of total RAM)
    total_mem_mb = psutil.virtual_memory().total / (1024 * 1024)
    mem_limit_mb = int(total_mem_mb * 0.85)
    
    # Dynamic worker calculation from gunicorn_conf logic
    cpus = multiprocessing.cpu_count()
    workers = min((2 * cpus) + 1, 4) # Hard cap at 4 for 500MB VPS
    
    content = f"""[Unit]
Description=RouteMaster V3 Nexus Gateway
After=network.target postgresql.service redis.service

[Service]
User={user}
Group={user}
WorkingDirectory={working_dir}
Environment="PATH={working_dir}/venv/bin"
EnvironmentFile={working_dir}/.env
ExecStart={working_dir}/venv/bin/gunicorn -c gunicorn_conf.py app:app

# Resilience Ops [Task 73]
Restart=always
RestartSec=5
StartLimitIntervalSec=0

# Resource Hardening [Task 73]
MemoryMax={mem_limit_mb}M
MemoryHigh={int(mem_limit_mb * 0.9)}M
CPUQuota=80%

# Security Hardening
PrivateTmp=true
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
"""
    
    service_path = Path("routemaster.service")
    with open(service_path, "w") as f:
        f.write(content)
    
    print(f"✅ Generated {service_path.absolute()}")
    print(f"👉 To install: sudo cp {service_path.absolute()} /etc/systemd/system/ && sudo systemctl enable --now routemaster")

def generate_start_script():
    """Generates an optimized production startup script."""
    content = """#!/bin/bash
# RouteMaster V3 Production Bootstrapper [Task 74]

echo "🚀 Initiating Nexus-100 Production Spine..."

# 1. Verify Venv
if [ ! -d "venv" ]; then
    echo "❌ Error: Virtual environment (venv) not found. Run setup first."
    exit 1
fi

# 2. Apply Migrations
echo "📦 Syncing Database Schema..."
./venv/bin/alembic upgrade head

# 3. Clean local tmp logs [Task 77]
echo "🧹 Cleaning temporary Nexus logs..."
rm -f /tmp/nexus_*.log
rm -f /tmp/nexus_healthy.lock

# 4. Start Gunicorn with the Spine Watchdog
echo "🔥 Igniting Gunicorn Master..."
./venv/bin/gunicorn -c gunicorn_conf.py app:app
"""
    
    script_path = Path("start_prod.sh")
    with open(script_path, "w") as f:
        f.write(content)
    
    # In a real environment, we'd chmod +x here
    print(f"✅ Generated {script_path.absolute()}")

if __name__ == "__main__":
    generate_systemd()
    generate_start_script()
