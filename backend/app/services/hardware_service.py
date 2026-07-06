import asyncio
import logging
import psutil
import json

logger = logging.getLogger("CAKRA_HARDWARE")

async def get_hardware_telemetry():
    """Fetch hardware metrics (GPU, CPU, RAM, Disk)"""
    telemetry = {
        "cpu_percent": 0.0,
        "ram_percent": 0.0,
        "ram_used_gb": 0.0,
        "ram_total_gb": 0.0,
        "gpu_percent": 0.0,
        "vram_used_gb": 0.0,
        "vram_total_gb": 0.0,
        "vram_percent": 0.0,
        "gpu_temp": 0.0,
        "gpu_name": "Unknown",
        "has_gpu": False
    }
    
    # 1. CPU & RAM (psutil)
    try:
        telemetry["cpu_percent"] = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()
        telemetry["ram_percent"] = mem.percent
        telemetry["ram_used_gb"] = round(mem.used / (1024**3), 2)
        telemetry["ram_total_gb"] = round(mem.total / (1024**3), 2)
    except Exception as e:
        logger.warning(f"Failed to fetch CPU/RAM telemetry: {e}")
        
    # 2. GPU (nvidia-smi)
    try:
        # Format: utilization.gpu, memory.used, memory.total, temperature.gpu, name
        cmd = "nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu,name --format=csv,noheader,nounits"
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        
        if proc.returncode == 0 and stdout:
            output = stdout.decode().strip().split('\n')[0]
            parts = [p.strip() for p in output.split(',')]
            if len(parts) >= 5:
                telemetry["has_gpu"] = True
                telemetry["gpu_percent"] = float(parts[0]) if parts[0].isdigit() else 0.0
                
                vram_used = float(parts[1]) if parts[1].isdigit() else 0.0
                vram_total = float(parts[2]) if parts[2].isdigit() else 0.0
                
                telemetry["vram_used_gb"] = round(vram_used / 1024, 2)
                telemetry["vram_total_gb"] = round(vram_total / 1024, 2)
                if vram_total > 0:
                    telemetry["vram_percent"] = round((vram_used / vram_total) * 100, 1)
                    
                telemetry["gpu_temp"] = float(parts[3]) if parts[3].isdigit() else 0.0
                telemetry["gpu_name"] = parts[4]
    except Exception as e:
        logger.warning(f"Failed to fetch GPU telemetry: {e}")
        
    return telemetry
