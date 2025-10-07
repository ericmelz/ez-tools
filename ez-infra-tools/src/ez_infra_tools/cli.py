"""CLI entry point for EZ Infrastructure Tools."""

import click

from ez_infra_tools import __version__


@click.group()
@click.version_option(version=__version__, prog_name="ez")
@click.pass_context
def main(ctx):
    """EZ Infrastructure Tools - Modern infrastructure management CLI.

    Manage secrets with SOPS/Age, K8s contexts, Helm deployments, and Nginx configurations.
    """
    ctx.ensure_object(dict)


@main.command()
@click.option("--name", default="World", help="Name to greet")
def hello(name):
    """Say hello - a simple hello world command."""
    click.echo(f"Hello, {name}!")
    click.echo("Welcome to EZ Infrastructure Tools!")


@main.group()
def secrets():
    """Manage secrets with SOPS and Age."""
    pass


@secrets.command(name="info")
def secrets_info():
    """Show secrets management info."""
    click.echo("Secrets management with SOPS and Age (coming soon)")


@main.group()
def k8s():
    """Manage Kubernetes contexts."""
    pass


@k8s.command(name="info")
def k8s_info():
    """Show K8s management info."""
    click.echo("Kubernetes context management (coming soon)")


@main.group()
def helm():
    """Manage Helm deployments."""
    pass


@helm.command(name="info")
def helm_info():
    """Show Helm management info."""
    click.echo("Helm deployment management (coming soon)")


@main.group()
def nginx():
    """Manage Nginx configurations."""
    pass


@nginx.command(name="info")
def nginx_info():
    """Show Nginx management info."""
    click.echo("Nginx configuration management (coming soon)")


if __name__ == "__main__":
    main()
