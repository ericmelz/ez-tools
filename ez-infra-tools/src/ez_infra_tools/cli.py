"""CLI entry point for EZ Infrastructure Tools."""

import sys

import click

from ez_infra_tools import __version__
from ez_infra_tools.secrets import sops_age
from ez_infra_tools.k8s import deploy as k8s_deploy


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


@secrets.command(name="setup")
@click.option("--project", help="Project subdirectory (creates if doesn't exist)")
@click.option("--environment", help="Environment name (e.g., dev, prod)")
def secrets_setup(project, environment):
    """Set up secrets management (generate age key, create config)."""
    if not sops_age.setup_secrets(project=project, environment=environment):
        sys.exit(1)


@secrets.command(name="edit")
@click.option("--project", help="Project subdirectory")
@click.option("--environment", help="Environment name (e.g., dev, prod)")
def secrets_edit(project, environment):
    """Edit encrypted secrets file."""
    if not sops_age.edit_secrets(project=project, environment=environment):
        sys.exit(1)


@secrets.command(name="decrypt")
@click.option("--format", type=click.Choice(["env", "yaml", "json"]), default="env", help="Output format")
@click.option("--key", help="Extract specific key only")
@click.option("--project", help="Project subdirectory")
@click.option("--environment", help="Environment name (e.g., dev, prod)")
def secrets_decrypt(format, key, project, environment):
    """Decrypt and display secrets."""
    if not sops_age.decrypt_secrets(output_format=format, key=key, project=project, environment=environment):
        sys.exit(1)


@secrets.command(name="check")
def secrets_check():
    """Check if sops and age are installed."""
    if not sops_age.check_dependencies():
        sys.exit(1)


@secrets.command(name="make-temp-secrets-yaml")
@click.option("--project", help="Project subdirectory")
@click.option("--environment", help="Environment name (e.g., dev, prod)")
def secrets_make_temp_yaml(project, environment):
    """Decrypt secrets and write to temporary YAML file with 'secrets:' wrapper."""
    if not sops_age.make_temp_secrets_yaml(project=project, environment=environment):
        sys.exit(1)


@main.group()
def k8s():
    """Manage Kubernetes contexts."""
    pass


@k8s.command(name="deploy")
@click.option("--project", required=True, help="Project name")
@click.option("--environment", help="Environment name (e.g., dev, prod)")
@click.option("--namespace", help="Kubernetes namespace (default: current context namespace)")
def k8s_deploy_chart(project, environment, namespace):
    """Deploy Helm chart with project and environment values."""
    if not k8s_deploy.deploy_helm_chart(project=project, environment=environment, namespace=namespace):
        sys.exit(1)


@k8s.command(name="undeploy")
@click.option("--project", required=True, help="Project name")
@click.option("--environment", help="Environment name (e.g., dev, prod)")
@click.option("--namespace", help="Kubernetes namespace (default: current context namespace)")
def k8s_undeploy_chart(project, environment, namespace):
    """Undeploy (uninstall) Helm release."""
    if not k8s_deploy.undeploy_helm_chart(project=project, environment=environment, namespace=namespace):
        sys.exit(1)


@k8s.command(name="create-test-pod")
@click.option("--namespace", default=None, help="Kubernetes namespace (default: current context namespace)")
def k8s_create_test_pod(namespace):
    """Create a test pod in the current Kubernetes context."""
    import subprocess
    import time

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

    pod_name = f"test-pod-{int(time.time())}"

    pod_yaml = f"""apiVersion: v1
kind: PersistentVolume
metadata:
  name: pv-notes-data-root
  namespace: {namespace}
spec:
  capacity:
    storage: 1Ti
  accessModes: [ReadWriteMany]
  storageClassName: ""                   # static
  persistentVolumeReclaimPolicy: Retain
  nfs:
    server: 192.168.2.6
    path: /volume1/notes_data/Joplin

---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: notes-data-pvc
  namespace: {namespace}
spec:
  storageClassName: ""   # empty to match the static PV
  accessModes:
    - ReadWriteMany
  resources:
    requests:
      storage: 20Gi

---
apiVersion: v1
kind: Pod
metadata:
  name: {pod_name}
  namespace: {namespace}
spec:
  dnsPolicy: ClusterFirst
  dnsConfig:
    options:
      - name: ndots
        value: "1"
  containers:
  - name: ubuntu
    image: ubuntu:24.04
    command: ["/bin/bash", "-c", "--"]
    args: ["while true; do sleep 30; done;"]
    volumeMounts:
    - name: notes-data
      mountPath: /notes_data
  volumes:
    - name: notes-data
      persistentVolumeClaim:
        claimName: notes-data-pvc
"""

    click.echo(f"Creating test pod '{pod_name}' in namespace '{namespace}'...")

    try:
        # Create the pod using kubectl
        result = subprocess.run(
            ["kubectl", "apply", "-f", "-"],
            input=pod_yaml,
            text=True,
            capture_output=True,
            check=True
        )

        click.echo(result.stdout)
        click.secho(f"✓ Test pod created successfully!", fg="green")
        click.echo(f"\nTo exec into the pod:")
        click.echo(f"  kubectl exec -it {pod_name} -n {namespace} -- /bin/bash")
        click.echo(f"\nTo delete the pod:")
        click.echo(f"  kubectl delete pod {pod_name} -n {namespace}")

    except subprocess.CalledProcessError as e:
        click.secho(f"✗ Failed to create test pod", fg="red", err=True)
        if e.stderr:
            click.echo(e.stderr, err=True)
        sys.exit(1)
    except FileNotFoundError:
        click.secho("✗ kubectl not found. Please install kubectl.", fg="red", err=True)
        sys.exit(1)


@k8s.command(name="delete-test-pod")
@click.option("--namespace", default=None, help="Kubernetes namespace (default: current context namespace)")
def k8s_delete_test_pod(namespace):
    """Delete test pod(s) from the specified namespace."""
    import subprocess
    import json

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

    click.echo(f"Searching for test pods in namespace '{namespace}'...")

    try:
        # Get all pods in the namespace that start with "test-pod-"
        result = subprocess.run(
            ["kubectl", "get", "pods", "-n", namespace, "-o", "json"],
            capture_output=True,
            text=True,
            check=True
        )

        pods_data = json.loads(result.stdout)
        test_pods = [
            pod["metadata"]["name"]
            for pod in pods_data.get("items", [])
            if pod["metadata"]["name"].startswith("test-pod-")
        ]

        if len(test_pods) == 0:
            click.secho(f"✓ No test pods found in namespace '{namespace}'", fg="green")
            return

        elif len(test_pods) == 1:
            pod_name = test_pods[0]
            click.echo(f"Found test pod: {pod_name}")
            click.echo(f"Deleting...")

            delete_result = subprocess.run(
                ["kubectl", "delete", "pod", pod_name, "-n", namespace],
                capture_output=True,
                text=True,
                check=True
            )

            click.echo(delete_result.stdout)
            click.secho(f"✓ Test pod deleted successfully!", fg="green")

        else:
            click.secho(f"Found {len(test_pods)} test pods in namespace '{namespace}':", fg="yellow")
            for pod in test_pods:
                click.echo(f"  - {pod}")

            click.echo(f"\nTo delete a specific pod, run:")
            for pod in test_pods:
                click.echo(f"  kubectl delete pod {pod} -n {namespace}")

            click.echo(f"\nTo delete all test pods:")
            click.echo(f"  kubectl delete pods -n {namespace} " + " ".join(test_pods))

    except subprocess.CalledProcessError as e:
        click.secho(f"✗ Failed to query or delete pods", fg="red", err=True)
        if e.stderr:
            click.echo(e.stderr, err=True)
        sys.exit(1)
    except FileNotFoundError:
        click.secho("✗ kubectl not found. Please install kubectl.", fg="red", err=True)
        sys.exit(1)
    except json.JSONDecodeError as e:
        click.secho(f"✗ Failed to parse kubectl output: {e}", fg="red", err=True)
        sys.exit(1)


@k8s.command(name="install-nfs-provisioner")
@click.option("--storage-class-name", required=True, help="Storage class name for NFS provisioner")
@click.option("--nfs-server", required=True, help="NFS server IP or hostname")
@click.option("--nfs-path", required=True, help="NFS export path")
@click.option("--default-class", is_flag=True, default=False, help="Set as default storage class")
@click.option("--namespace", default="kube-system", help="Namespace to install provisioner (default: kube-system)")
def k8s_install_nfs_provisioner(storage_class_name, nfs_server, nfs_path, default_class, namespace):
    """Install NFS subdir external provisioner using Helm."""
    import subprocess

    click.echo("Installing NFS subdir external provisioner...")
    click.echo(f"  Storage Class: {storage_class_name}")
    click.echo(f"  NFS Server: {nfs_server}")
    click.echo(f"  NFS Path: {nfs_path}")
    click.echo(f"  Namespace: {namespace}")
    click.echo(f"  Default Class: {default_class}")
    click.echo()

    try:
        # Check if helm is installed
        subprocess.run(
            ["helm", "version", "--short"],
            capture_output=True,
            check=True
        )
    except FileNotFoundError:
        click.secho("✗ helm not found. Please install helm.", fg="red", err=True)
        click.echo("\nInstall with: brew install helm", err=True)
        sys.exit(1)
    except subprocess.CalledProcessError:
        click.secho("✗ Failed to check helm version.", fg="red", err=True)
        sys.exit(1)

    try:
        # Add helm repo
        click.echo("Adding helm repository...")
        subprocess.run(
            ["helm", "repo", "add", "nfs-subdir-external-provisioner",
             "https://kubernetes-sigs.github.io/nfs-subdir-external-provisioner"],
            check=True,
            capture_output=True
        )

        # Update helm repos
        click.echo("Updating helm repositories...")
        subprocess.run(
            ["helm", "repo", "update"],
            check=True,
            capture_output=True
        )

        # Install/upgrade the provisioner
        click.echo("Installing NFS provisioner...")
        cmd = [
            "helm", "upgrade", "--install", "nfs-provisioner",
            "nfs-subdir-external-provisioner/nfs-subdir-external-provisioner",
            "--namespace", namespace,
            "--create-namespace",
            "--set", f"nfs.server={nfs_server}",
            "--set", f"nfs.path={nfs_path}",
            "--set", f"storageClass.name={storage_class_name}",
            "--set", f"storageClass.defaultClass={str(default_class).lower()}",
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )

        click.echo(result.stdout)
        click.secho("\n✓ NFS provisioner installed successfully!", fg="green")

        click.echo("\nTo verify the installation:")
        click.echo(f"  kubectl get pods -n {namespace} -l app=nfs-subdir-external-provisioner")
        click.echo(f"  kubectl get storageclass {storage_class_name}")

        click.echo("\nTo test the provisioner, create a PVC:")
        click.echo(f"""
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: test-pvc
spec:
  storageClassName: {storage_class_name}
  accessModes:
    - ReadWriteMany
  resources:
    requests:
      storage: 1Gi
""")

    except subprocess.CalledProcessError as e:
        click.secho("✗ Failed to install NFS provisioner", fg="red", err=True)
        if e.stderr:
            click.echo(e.stderr, err=True)
        if e.stdout:
            click.echo(e.stdout, err=True)
        sys.exit(1)


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
