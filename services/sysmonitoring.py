from __future__ import annotations
import os, re, sys, time, signal
from collections import namedtuple
from typing import Tuple
from rich.console import Console
from rich.live import Live
from rich.text import Text

console = Console(highlight=False)
status_line = Text("", style="bold", no_wrap=True)

Prev = namedtuple("Prev",
    "cpu_idle cpu_total disk_read disk_write net_rx net_tx time")
prev = Prev(0, 0, 0, 0, 0, 0, time.time())

def read_cpu_times() -> Tuple[int, int]:
    with open("/proc/stat") as f:
        v = list(map(int, f.readline().split()[1:]))
    return v[3] + v[4], sum(v)

def read_mem_percent() -> float:
    info: dict[str, int] = {}
    with open("/proc/meminfo") as f:
        for line in f:
            k, v = line.split(":")[0], int(line.split()[1])
            info[k] = v
    total = info.get("MemTotal", 0)
    avail = info.get("MemAvailable",
                     info.get("MemFree", 0)
                     + info.get("Buffers", 0)
                     + info.get("Cached", 0))
    return (total - avail) * 100 / total if total else 0.0

def read_disk_usage_percent(path: str = "/") -> float:
    st = os.statvfs(path)
    total = st.f_blocks * st.f_frsize
    avail = st.f_bavail * st.f_frsize
    return (total - avail) * 100 / total if total else 0.0

_DEV_RX = re.compile(r"^(sd[a-z]|hd[a-z]|nvme\d+n\d+)$")
def read_disk_io() -> Tuple[float, float]:
    rd = wr = 0
    with open("/proc/diskstats") as f:
        for parts in (ln.split() for ln in f):
            if _DEV_RX.match(parts[2]):
                rd += int(parts[5])
                wr += int(parts[9])
    return rd * 512 / 1024**2, wr * 512 / 1024**2 

def read_net_dev() -> Tuple[float, float]:
    rx = tx = 0
    with open("/proc/net/dev") as f:
        next(f); next(f)
        for line in f:
            iface, data = line.split(":", 1)
            if iface.strip() == "lo":
                continue
            vals = list(map(int, data.split()))
            rx += vals[0]; tx += vals[8]
    return rx / 1024, tx / 1024

def make_status() -> str:
    global prev
    idle1, total1 = read_cpu_times()
    rd1, wr1      = read_disk_io()
    rx1, tx1      = read_net_dev()

    dt = max(time.time() - prev.time, 1e-3)
    cpu_pct  = (1 - (idle1 - prev.cpu_idle)/(total1 - prev.cpu_total)) * 100
    ram_pct  = read_mem_percent()
    disk_pct = read_disk_usage_percent("/")

    line = (
        f"CPU:{cpu_pct:5.1f}% "
        f"RAM:{ram_pct:5.1f}% "
        f"DISK:{disk_pct:5.1f}% "
        f"I/O R:{(rd1-prev.disk_read)/dt:6.2f}MB/s "
        f"W:{(wr1-prev.disk_write)/dt:6.2f}MB/s "
        f"NET ↑{(tx1-prev.net_tx)/dt:6.2f}KB/s "
        f"↓{(rx1-prev.net_rx)/dt:6.2f}KB/s"
    )

    prev = Prev(idle1, total1, rd1, wr1, rx1, tx1, time.time())
    return line

signal.signal(signal.SIGINT, lambda *_: (console.print(), sys.exit(0)))

def main() -> None:
    with Live(status_line, console=console,
              screen=False, refresh_per_second=1,
              vertical_overflow="crop",
              redirect_stdout=True, redirect_stderr=True) as live:
        while True:
            output_text = make_status()
            status_line.plain = output_text.ljust(console.width)
            live.update(status_line) 
            time.sleep(1)

if __name__ == "__main__":
    main()
