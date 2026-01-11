import click

from mnemosyne.aletheia.email_ingest import email_ingest_cli
from mnemosyne.aletheia.pdf_ingestor import pdf_ingest_cli
from mnemosyne.cli.checkpoints import checkpoints_cli
from mnemosyne.cli.cluster import cluster_cli
from mnemosyne.cli.config import config_cli
from mnemosyne.cli.graph_taxonomy import graph_taxonomy_cli
from mnemosyne.cli.hermes import hermes_cli
from mnemosyne.cli.ingest import ingest_cli
from mnemosyne.cli.monitor import monitor_cli
from mnemosyne.cli.quality import quality_cli
from mnemosyne.cli.scheduler import scheduler_cli
from mnemosyne.cli.scout import scout_cli


@click.group()
def mnemosyne_cli():
    """Mnemosyne CLI"""
    pass


mnemosyne_cli.add_command(config_cli)
mnemosyne_cli.add_command(cluster_cli, name="cluster")
mnemosyne_cli.add_command(ingest_cli, name="ingest")
mnemosyne_cli.add_command(scout_cli, name="scout")
mnemosyne_cli.add_command(monitor_cli, name="monitor")
mnemosyne_cli.add_command(graph_taxonomy_cli, name="graph-taxonomy")
mnemosyne_cli.add_command(quality_cli, name="quality")
mnemosyne_cli.add_command(hermes_cli, name="hermes")
mnemosyne_cli.add_command(scheduler_cli, name="scheduler")
mnemosyne_cli.add_command(checkpoints_cli, name="checkpoints")
mnemosyne_cli.add_command(email_ingest_cli, name="email-ingest")
mnemosyne_cli.add_command(pdf_ingest_cli, name="pdf-ingest")

if __name__ == "__main__":
    mnemosyne_cli()
