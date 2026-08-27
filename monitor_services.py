#!/usr/bin/env python3
"""
=============================================================================
  🌟 CAKRA AI - LIVE SERVICES MONITOR & REAL-TIME LOG STREAMER
=============================================================================
Menampilkan status kesehatan seluruh microservices CAKRA AI serta
melakukan tail multi-service log secara live dengan pewarnaan terminal yang rapi.
"""

import os
import sys
import time
import argparse
import asyncio
import httpx
from datetime import datetime

# ANSI Color codes for beautiful terminal UI
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
WHITE = "\033[37m"
BG_BLUE = "\033[44m"
BG_MAGENTA = "\033[45m"
BG_DARK = "\033[40m"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOGS_DIR = os.path.join(BASE_DIR, "logs", "services")

SERVICES = [
    {
        "name": "Chat Service",
        "port": 8001,
        "url": "http://localhost:8001/docs",
        "log_file": "chat_service.log",
        "pid_file": "chat_service.pid",
        "badge": f"{BG_MAGENTA}{WHITE}{BOLD} CHAT {RESET}",
        "color": MAGENTA,
    },
    {
        "name": "API Gateway",
        "port": 8000,
        "url": "http://localhost:8000/docs",
        "log_file": "gateway.log",
        "pid_file": "gateway.pid",
        "badge": f"{BG_BLUE}{WHITE}{BOLD} GTWY {RESET}",
        "color": BLUE,
    },
    {
        "name": "Analytics Service",
        "port": 8002,
        "url": "http://localhost:8002/docs",
        "log_file": "analytics_service.log",
        "pid_file": "analytics_service.pid",
        "badge": f"{YELLOW}{BOLD}[ANALYTICS]{RESET}",
        "color": YELLOW,
    },
    {
        "name": "Auth Service",
        "port": 8003,
        "url": "http://localhost:8003/docs",
        "log_file": "auth_service.log",
        "pid_file": "auth_service.pid",
        "badge": f"{CYAN}{BOLD}[AUTH]{RESET}",
        "color": CYAN,
    },
    {
        "name": "Frontend WebUI",
        "port": 5173,
        "url": "http://localhost:5173",
        "log_file": "frontend.log",
        "pid_file": "frontend.pid",
        "badge": f"{GREEN}{BOLD}[WEBUI]{RESET}",
        "color": GREEN,
    },
]


def check_pid(pid: int) -> bool:
    """Cek apakah PID masih aktif berjalan di OS."""
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


async def check_service_health(svc: dict) -> dict:
    """Cek status port, PID, dan respons HTTP endpoint."""
    pid_path = os.path.join(LOGS_DIR, svc["pid_file"])
    pid = None
    is_pid_alive = False
    if os.path.exists(pid_path):
        try:
            with open(pid_path, "r") as f:
                pid = int(f.read().strip())
                is_pid_alive = check_pid(pid)
        except Exception:
            pass

    http_ok = False
    status_code = None
    try:
        async with httpx.AsyncClient(timeout=1.2) as client:
            resp = await client.get(svc["url"])
            if resp.status_code in [200, 307, 404]:
                http_ok = True
                status_code = resp.status_code
    except Exception:
        http_ok = False

    return {
        "name": svc["name"],
        "port": svc["port"],
        "pid": pid,
        "pid_alive": is_pid_alive,
        "http_ok": http_ok,
        "status_code": status_code,
    }


async def print_dashboard():
    """Tampilkan header dashboard ringkas."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n{BOLD}{CYAN}════════════════════════════════════════════════════════════════════════════════════════{RESET}")
    print(f"  {BOLD}🛡️  CAKRA AI - MICROSERVICES LIVE MONITORING SYSTEM{RESET}  {DIM}({now}){RESET}")
    print(f"{BOLD}{CYAN}════════════════════════════════════════════════════════════════════════════════════════{RESET}")

    tasks = [check_service_health(svc) for svc in SERVICES]
    results = await asyncio.gather(*tasks)

    for r in results:
        status_badge = f"{GREEN}● RUNNING{RESET}" if (r["pid_alive"] or r["http_ok"]) else f"{RED}✖ STOPPED{RESET}"
        pid_str = f"PID: {r['pid']}" if r["pid"] else "PID: -"
        port_str = f"Port: {r['port']}"
        print(f"  {status_badge:<20} {BOLD}{r['name']:<20}{RESET} {DIM}{port_str:<12} {pid_str:<12}{RESET}")

    print(f"{BOLD}{CYAN}────────────────────────────────────────────────────────────────────────────────────────{RESET}")
    print(f"  {YELLOW}📡 Live Log Stream Active... (Tekan Ctrl+C untuk keluar){RESET}\n")


def colorize_log_line(line: str) -> str:
    """Format dan warnai log keyword penting."""
    if "[CALL1]" in line or "CAKRA_ROUTER" in line:
        return f"{YELLOW}{line}{RESET}"
    if "[CALL2" in line or "[GEMMA_ANSWER]" in line:
        return f"{GREEN}{line}{RESET}"
    if "ERROR" in line or "Traceback" in line or "Exception" in line:
        return f"{RED}{BOLD}{line}{RESET}"
    if "WARNING" in line:
        return f"{YELLOW}{line}{RESET}"
    if "INFO" in line:
        return f"{WHITE}{line}{RESET}"
    return f"{DIM}{line}{RESET}"


async def stream_logs(selected_services=None, lines_history=15):
    """Lakukan live tailing multi-service log."""
    if not selected_services:
        selected_services = SERVICES

    # Simpan pointer posisi file
    file_handles = {}
    for svc in selected_services:
        log_path = os.path.join(LOGS_DIR, svc["log_file"])
        if os.path.exists(log_path):
            f = open(log_path, "r", encoding="utf-8", errors="replace")
            # Baca beberapa baris terakhir sebagai inisialisasi
            lines = f.readlines()
            for l in lines[-lines_history:]:
                l_clean = l.strip()
                if l_clean:
                    print(f"{svc['badge']} {colorize_log_line(l_clean)}")
            file_handles[svc["name"]] = (f, svc)
        else:
            print(f"{svc['badge']} {DIM}[File log belum terbentuk: {svc['log_file']}]{RESET}")

    # Loop polling non-blocking
    while True:
        had_output = False
        for name, (f, svc) in list(file_handles.items()):
            line = f.readline()
            while line:
                had_output = True
                l_clean = line.strip()
                if l_clean:
                    print(f"{svc['badge']} {colorize_log_line(l_clean)}", flush=True)
                line = f.readline()
        
        # Cek jika ada file log yang baru dibuat
        for svc in selected_services:
            if svc["name"] not in file_handles:
                log_path = os.path.join(LOGS_DIR, svc["log_file"])
                if os.path.exists(log_path):
                    f = open(log_path, "r", encoding="utf-8", errors="replace")
                    file_handles[svc["name"]] = (f, svc)

        await asyncio.sleep(0.3)


async def main():
    parser = argparse.ArgumentParser(description="CAKRA AI Services Live Monitor")
    parser.add_argument("--be", "--backend", action="store_true", help="Hanya monitor seluruh Backend Services (Chat, Gateway, Analytics, Auth)")
    parser.add_argument("--chat", action="store_true", help="Hanya monitor Chat Service (Call 1 Router & Call 2 LLM)")
    parser.add_argument("--gateway", action="store_true", help="Hanya monitor API Gateway")
    parser.add_argument("--status", action="store_true", help="Hanya cek status kesehatan tanpa live streaming")
    args = parser.parse_args()

    await print_dashboard()

    if args.status:
        return

    selected = None
    if args.chat:
        selected = [s for s in SERVICES if s["name"] == "Chat Service"]
    elif args.gateway:
        selected = [s for s in SERVICES if s["name"] == "API Gateway"]
    elif args.be:
        # Seluruh Backend (tanpa Frontend WebUI)
        selected = [s for s in SERVICES if s["name"] != "Frontend WebUI"]

    try:
        await stream_logs(selected)
    except (KeyboardInterrupt, asyncio.CancelledError):
        print(f"\n{YELLOW}👋 Monitoring dihentikan oleh user.{RESET}\n")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
