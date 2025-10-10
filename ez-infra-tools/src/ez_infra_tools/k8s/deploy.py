"""Helm chart deployment utilities."""

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

import click

from ez_infra_tools.secrets import sops_age


def info(message: str) -> None:
    """Print info message in green."""
    click.secho(f"[INFO] {message}", fg="green", err=True)


def warn(message: str) -> None:
    """Print warning message in yellow."""
    click.secho(f"[WARN] {message}", fg="yellow", err=True)


def error(message: str) -> None:
    """Print error message in red."""
    click.secho(f"[ERROR] {message}", fg="red", err=True)


def undeploy_helm_chart(project: str, environment: Optional[str] = None, namespace: Optional[str] = None) -> bool:
    """Undeploy (uninstall) a Helm release.

    Args:
        project: Project name (required)
        environment: Environment name (e.g., dev, prod)
        namespace: Kubernetes namespace (defaults to current context namespace)

    Returns:
        True if successful, False otherwise
    """
    # Get current namespace from kubeconfig if not specified
    if namespace is None:
        try:
            result = subprocess.run(
                ["kubectl", "config", "view", "--minify", "--output", "jsonpath={..namespace}"],
                capture_output=True,
                text=True,
                check=True
            )
            namespace = result.stdout.strip()
            if not namespace:
                namespace = "default"
        except subprocess.CalledProcessError:
            namespace = "default"

    info(f"Target namespace: {namespace}")

    # Build release name
    release_name = project
    if environment:
        release_name = f"{project}-{environment}"

    info(f"Undeploying Helm release: {release_name}")

    # Execute helm uninstall
    helm_cmd = ["helm", "uninstall", release_name, "--namespace", namespace]

    info(f"Executing: {' '.join(helm_cmd)}")

    try:
        result = subprocess.run(
            helm_cmd,
            capture_output=True,
            text=True,
            check=True
        )

        click.echo(result.stdout)
        click.secho(f"✓ Successfully undeployed {release_name} from namespace {namespace}", fg="green")
        return True

    except subprocess.CalledProcessError as e:
        error(f"Failed to undeploy Helm release: {e}")
        if e.stdout:
            click.echo(e.stdout, err=True)
        if e.stderr:
            click.echo(e.stderr, err=True)
        return False
    except FileNotFoundError:
        error("helm not found. Please install helm.")
        click.echo("\nInstall with: brew install helm", err=True)
        return False


def deploy_helm_chart(project: str, environment: Optional[str] = None, namespace: Optional[str] = None) -> bool:
    """Deploy a Helm chart with project and environment-specific values.

    Args:
        project: Project name (required)
        environment: Environment name (e.g., dev, prod)
        namespace: Kubernetes namespace (defaults to current context namespace)

    Returns:
        True if successful, False otherwise
    """
    base_dir = Path.cwd() / project
    helm_dir = base_dir / "helm"

    # Validate that helm directory exists
    if not helm_dir.exists():
        error(f"Helm directory not found: {helm_dir}")
        return False

    chart_yaml = helm_dir / "Chart.yaml"
    if not chart_yaml.exists():
        error(f"Chart.yaml not found: {chart_yaml}")
        return False

    info(f"Deploying Helm chart from: {helm_dir}")

    # Get current namespace from kubeconfig if not specified
    if namespace is None:
        try:
            result = subprocess.run(
                ["kubectl", "config", "view", "--minify", "--output", "jsonpath={..namespace}"],
                capture_output=True,
                text=True,
                check=True
            )
            namespace = result.stdout.strip()
            if not namespace:
                namespace = "default"
        except subprocess.CalledProcessError:
            namespace = "default"

    info(f"Target namespace: {namespace}")

    # Build helm command
    release_name = project
    if environment:
        release_name = f"{project}-{environment}"

    helm_cmd = [
        "helm", "upgrade", "--install",
        release_name,
        str(helm_dir),
        "--namespace", namespace,
        "--create-namespace"
    ]

    # Add base values.yaml if it exists in helm directory
    base_values = helm_dir / "values.yaml"
    if base_values.exists():
        info(f"Using base values: {base_values}")
        helm_cmd.extend(["-f", str(base_values)])

    # Add environment-specific values.yaml if environment is specified
    if environment:
        env_values = base_dir / "environments" / environment / "values.yaml"
        if env_values.exists():
            info(f"Using environment values: {env_values}")
            helm_cmd.extend(["-f", str(env_values)])
        else:
            warn(f"Environment values file not found: {env_values}")

        # Generate temporary secrets file and include it
        info("Generating temporary secrets file...")

        # Change to project directory for secrets operations
        original_dir = Path.cwd()
        os.chdir(base_dir.parent)

        try:
            if sops_age.make_temp_secrets_yaml(project=project, environment=environment):
                secrets_file = Path(f"/tmp/{project}-{environment}-secret-values.yaml")
                if secrets_file.exists():
                    info(f"Using secrets values: {secrets_file}")
                    helm_cmd.extend(["-f", str(secrets_file)])
                else:
                    warn("Secrets file was not created, continuing without secrets")
            else:
                warn("Failed to generate secrets file, continuing without secrets")
        finally:
            os.chdir(original_dir)

    # Execute helm upgrade --install
    info(f"Executing: {' '.join(helm_cmd)}")

    try:
        result = subprocess.run(
            helm_cmd,
            capture_output=True,
            text=True,
            check=True
        )

        click.echo(result.stdout)
        click.secho(f"✓ Successfully deployed {release_name} to namespace {namespace}", fg="green")

        # Clean up temporary secrets file if it exists
        if environment:
            secrets_file = Path(f"/tmp/{project}-{environment}-secret-values.yaml")
            if secrets_file.exists():
                try:
                    secrets_file.unlink()
                    info(f"Cleaned up temporary secrets file: {secrets_file}")
                except Exception as e:
                    warn(f"Failed to clean up temporary secrets file: {e}")

        return True

    except subprocess.CalledProcessError as e:
        error(f"Failed to deploy Helm chart: {e}")
        if e.stdout:
            click.echo(e.stdout, err=True)
        if e.stderr:
            click.echo(e.stderr, err=True)

        # Clean up temporary secrets file on error
        if environment:
            secrets_file = Path(f"/tmp/{project}-{environment}-secret-values.yaml")
            if secrets_file.exists():
                try:
                    secrets_file.unlink()
                except Exception:
                    pass

        return False
    except FileNotFoundError:
        error("helm not found. Please install helm.")
        click.echo("\nInstall with: brew install helm", err=True)
        return False
