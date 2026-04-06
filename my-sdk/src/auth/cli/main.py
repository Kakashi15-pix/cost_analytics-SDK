import click
import json
import signal
import sys
from auth.device_flow import login
from auth.handshake import perform
from connection.sse_client import SSEClient
from ingest.poller import CostPoller
from credentials import save, load, clear

@click.group()
def cli():
    pass

@cli.command()
def login_cmd():
    """Authenticate and provision SDK connection."""
    click.echo("Starting login...")
    tokens = login()
    click.echo("Approved. Running handshake...")
    setup = perform(tokens["access_token"])
    save({
        "api_key": setup["api_key"],
        "tenant_id": setup["tenant_id"],
        "stream_endpoint": setup["stream_endpoint"],
        "ingest_endpoint": setup["ingest_endpoint"]
    })
    click.echo(f"✓ Authenticated as tenant {setup['tenant_id']}")
    click.echo("Run `costsdk start` to begin monitoring.")

@cli.command()
def start():
    """Start 24/7 cost monitoring."""
    try:
        creds = load()
    except FileNotFoundError as e:
        click.echo(str(e))
        sys.exit(1)

    click.echo(f"✓ Starting monitor for tenant {creds['tenant_id']}")

    def on_event(event):
        data = json.loads(event["data"])
        click.echo(f"[{event['type']}] {data}")

    def on_connect():
        click.echo("✓ Stream connected.")

    def on_disconnect(err):
        click.echo(f"✗ Stream dropped: {err}. Reconnecting...")

    sse = SSEClient(on_event=on_event, on_connect=on_connect, on_disconnect=on_disconnect)
    poller = CostPoller()

    sse.start()
    poller.start()

    def shutdown(sig, frame):
        click.echo("\nShutting down...")
        sse.stop()
        poller.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    signal.pause()

@cli.command()
def logout():
    """Revoke credentials."""
    clear()
    click.echo("✓ Logged out.")

if __name__ == "__main__":
    cli(prog_name="costsdk")