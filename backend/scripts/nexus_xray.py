#!/usr/bin/env python3
import requests
import time
import os
import sys
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.panel import Panel
from rich.layout import Layout
from rich import box

console = Console()

class NexusXRayCLI:
    """
    [Task 96] Elite CLI Dashboard for Nexus Spine.
    Works directly via API or Local Socket (if available).
    """
    def __init__(self, endpoint: str = "http://127.0.0.1:8000/api/v3/governor/stats"):
        self.endpoint = endpoint

    def _fetch_stats(self):
        try:
            resp = requests.get(self.endpoint, timeout=2)
            if resp.status_code == 200:
                return resp.json()
            return None
        except:
            return None

    def generate_layout(self, stats) -> Layout:
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body", ratio=1),
            Layout(name="footer", size=3)
        )
        
        # Header
        layout["header"].update(Panel(f"[bold white]NEXUS-100 X-RAY: VPS DIAGNOSTICS[/bold white] | [cyan]Target: {self.endpoint}[/cyan]", style="blue", box=box.ROUNDED))
        
        # Body (Split into Resources and Governor)
        body = Layout()
        body.split_row(
            Layout(name="resources"),
            Layout(name="governor")
        )
        layout["body"].update(body)
        
        if not stats:
            body["resources"].update(Panel("[red]SERVICE UNREACHABLE[/red]", title="Vitals"))
            body["governor"].update(Panel("[red]OFFLINE[/red]", title="Governor Status"))
            return layout

        # Resources Table
        res_table = Table(show_header=True, header_style="bold magenta", box=box.SIMPLE)
        res_table.add_column("Metric")
        res_table.add_column("Value")
        res_table.add_column("Status")
        
        vps = stats["vps"]
        res_table.add_row("CPU Load", f"{vps['cpu_p']}%", "[green]HEALTHY[/green]" if vps['cpu_p'] < 70 else "[yellow]LAGGING[/yellow]")
        res_table.add_row("RAM Usage", f"{vps['ram_p']}%", "[green]STABLE[/green]" if vps['ram_p'] < 85 else "[red]CRITICAL[/red]")
        res_table.add_row("IO Wait", f"{vps['io_wait_p']}%", "Nominal" if vps['io_wait_p'] < 10 else "[bold red]IO_PRESSURE[/bold red]")
        res_table.add_row("Redis Mem", f"{vps['redis_p']:.1f}%", "OK" if vps['redis_p'] < 80 else "PURGING")
        
        body["resources"].update(Panel(res_table, title="[yellow]VPS Vitals[/yellow]"))
        
        # Governor Table
        gov_table = Table(show_header=True, header_style="bold cyan", box=box.SIMPLE)
        gov_table.add_column("Property")
        gov_table.add_column("Value")
        
        gov = stats["governor"]
        gov_table.add_row("Throttle Factor", f"{gov['throttle_factor']*100:.1f}%")
        gov_table.add_row("System Status", f"[bold]{stats['system_status']}[/bold]")
        gov_table.add_row("Ghost Mode", "ACTIVE" if stats['system_status'] == "SEVERED" else "OFF")
        gov_table.add_row("Backoff", f"{gov['backoff_factor']:.3f}")
        
        body["governor"].update(Panel(gov_table, title="[cyan]Governor Engine[/cyan]"))
        
        # Footer
        layout["footer"].update(Panel(f"Last Pulse: {time.ctime(stats['timestamp'])} | [bold green]PRESS CTRL+C TO EXIT[/bold green]", box=box.MINIMAL))
        
        return layout

    def run(self):
        with Live(console=console, screen=True, auto_refresh=False) as live:
            while True:
                stats = self._fetch_stats()
                layout = self.generate_layout(stats)
                live.update(layout, refresh=True)
                time.sleep(2)

if __name__ == "__main__":
    cli = NexusXRayCLI()
    try:
        cli.run()
    except KeyboardInterrupt:
        console.print("[bold red]NEXUS-XRAY Session Terminated.[/bold red]")
