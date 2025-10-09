"""SOPS and Age encryption utilities for secrets management."""

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

import click


def get_project_root(project: Optional[str] = None) -> Path:
    """Get the project root directory.

    Args:
        project: Optional subdirectory name relative to current working directory

    Returns:
        Path to project root (either cwd or cwd/project)
    """
    base = Path.cwd()
    if project:
        return base / project
    return base


def get_secrets_dir(project: Optional[str] = None) -> Path:
    """Get the secrets directory path.

    Args:
        project: Optional subdirectory name
    """
    return get_project_root(project) / "secrets"


def get_age_key_path(project: Optional[str] = None) -> Path:
    """Get the age key file path.

    Args:
        project: Optional subdirectory name
    """
    return get_secrets_dir(project) / "age-key.txt"


def get_secrets_path(project: Optional[str] = None) -> Path:
    """Get the secrets YAML file path.

    Args:
        project: Optional subdirectory name
    """
    return get_secrets_dir(project) / "secrets.yaml"


def info(message: str) -> None:
    """Print info message in green."""
    click.secho(f"[INFO] {message}", fg="green", err=True)


def warn(message: str) -> None:
    """Print warning message in yellow."""
    click.secho(f"[WARN] {message}", fg="yellow", err=True)


def error(message: str) -> None:
    """Print error message in red."""
    click.secho(f"[ERROR] {message}", fg="red", err=True)


def check_dependencies() -> bool:
    """Check if sops and age are installed."""
    info("Checking dependencies...")

    missing = []

    try:
        subprocess.run(["sops", "--version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        missing.append("sops")

    try:
        subprocess.run(["age", "--version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        missing.append("age")

    if missing:
        error(f"Missing required tools: {', '.join(missing)}")
        click.echo("\nInstall with:", err=True)
        for tool in missing:
            click.echo(f"  brew install {tool}", err=True)
        return False

    info("All dependencies are installed.")
    return True


def generate_age_key(project: Optional[str] = None) -> Optional[str]:
    """Generate an age key if it doesn't exist. Returns the public key.

    Args:
        project: Optional subdirectory name
    """
    age_key_file = get_age_key_path(project)
    secrets_dir = get_secrets_dir(project)

    if age_key_file.exists():
        info(f"Age key already exists: {age_key_file}")
        # Extract and return public key
        try:
            with open(age_key_file, 'r') as f:
                for line in f:
                    if line.startswith("# public key:"):
                        return line.split(":")[1].strip()
        except Exception as e:
            error(f"Failed to read public key: {e}")
            return None

    info("Generating new age key...")
    secrets_dir.mkdir(parents=True, exist_ok=True)

    try:
        result = subprocess.run(
            ["age-keygen", "-o", str(age_key_file)],
            capture_output=True,
            text=True,
            check=True
        )

        # Set restrictive permissions
        os.chmod(age_key_file, 0o600)

        info(f"Age key generated: {age_key_file}")
        warn("IMPORTANT: Store this key securely and add to your password manager!")

        # Extract public key from output
        for line in result.stderr.split('\n'):
            if line.startswith("Public key:"):
                public_key = line.split(":")[1].strip()
                click.echo(f"\nPublic key for .sops.yaml:\n{public_key}\n", err=True)
                return public_key

        # Try reading from file
        with open(age_key_file, 'r') as f:
            for line in f:
                if line.startswith("# public key:"):
                    public_key = line.split(":")[1].strip()
                    click.echo(f"\nPublic key for .sops.yaml:\n{public_key}\n", err=True)
                    return public_key

        return None

    except subprocess.CalledProcessError as e:
        error(f"Failed to generate age key: {e}")
        if e.stderr:
            click.echo(e.stderr, err=True)
        return None


def create_sops_config(public_key: str, project: Optional[str] = None) -> bool:
    """Create .sops.yaml configuration file.

    Args:
        public_key: Age public key
        project: Optional subdirectory name
    """
    sops_config_path = get_project_root(project) / ".sops.yaml"

    if sops_config_path.exists():
        info(f".sops.yaml already exists: {sops_config_path}")
        return True

    config_content = f"""keys:
 - &age_key {public_key}
creation_rules:
 - path_regex: secrets/.*\\.yaml$
   age: *age_key
"""

    try:
        with open(sops_config_path, 'w') as f:
            f.write(config_content)
        info(f"Created .sops.yaml: {sops_config_path}")
        return True
    except Exception as e:
        error(f"Failed to create .sops.yaml: {e}")
        return False


def create_initial_secrets_file(project: Optional[str] = None) -> bool:
    """Create an initial encrypted secrets file.

    Args:
        project: Optional subdirectory name
    """
    secrets_file = get_secrets_path(project)
    age_key_file = get_age_key_path(project)

    if secrets_file.exists():
        info(f"Secrets file already exists: {secrets_file}")
        return True

    info("Creating initial encrypted secrets file...")

    # Create initial unencrypted content
    initial_content = """# Add your secrets here in YAML format
# Example structure below:
database:
  username: ""
  password: ""
api:
  key: ""
  secret: ""
"""

    secrets_dir = get_secrets_dir(project)
    secrets_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Write initial content directly to final file
        with open(secrets_file, 'w') as f:
            f.write(initial_content)

        # Encrypt with sops in-place
        env = os.environ.copy()
        env['SOPS_AGE_KEY_FILE'] = str(age_key_file)

        sops_config = get_project_root(project) / ".sops.yaml"
        cmd = ["sops", "--config", str(sops_config), "--encrypt", "--in-place", str(secrets_file)]

        subprocess.run(
            cmd,
            env=env,
            check=True,
            capture_output=True
        )

        info(f"Created encrypted secrets file: {secrets_file}")
        return True

    except subprocess.CalledProcessError as e:
        error(f"Failed to create encrypted secrets file: {e}")
        if e.stderr:
            click.echo(e.stderr.decode(), err=True)
        # Clean up unencrypted file if encryption failed
        if secrets_file.exists():
            secrets_file.unlink()
        return False
    except Exception as e:
        error(f"Failed to create secrets file: {e}")
        return False


def setup_secrets(project: Optional[str] = None) -> bool:
    """Complete setup process for secrets management.

    Args:
        project: Optional subdirectory name
    """
    if not check_dependencies():
        return False

    # Create project directory if it doesn't exist
    if project:
        project_root = get_project_root(project)
        project_root.mkdir(parents=True, exist_ok=True)
        info(f"Using project directory: {project_root}")

    public_key = generate_age_key(project)
    if not public_key:
        error("Failed to generate or read age key")
        return False

    if not create_sops_config(public_key, project):
        return False

    if not create_initial_secrets_file(project):
        return False

    info("\nSecrets setup complete!")
    info(f"Age key: {get_age_key_path(project)}")
    info(f"Secrets file: {get_secrets_path(project)}")
    info(f"SOPS config: {get_project_root(project) / '.sops.yaml'}")

    project_suffix = f" --project {project}" if project else ""
    click.echo("\nNext steps:", err=True)
    click.echo("  1. Backup your age key to a secure location", err=True)
    click.echo(f"  2. Edit secrets with: ez secrets edit{project_suffix}", err=True)
    click.echo(f"  3. Decrypt secrets with: ez secrets decrypt{project_suffix}", err=True)

    return True


def edit_secrets(project: Optional[str] = None) -> bool:
    """Edit encrypted secrets file using SOPS.

    Args:
        project: Optional subdirectory name
    """
    secrets_file = get_secrets_path(project)
    age_key_file = get_age_key_path(project)

    if not secrets_file.exists():
        error(f"Encrypted secrets file not found: {secrets_file}")
        click.echo("Run 'ez secrets setup' first", err=True)
        return False

    if not age_key_file.exists():
        error(f"Age key file not found: {age_key_file}")
        click.echo("Run 'ez secrets setup' first", err=True)
        return False

    info("Opening encrypted secrets file for editing...")
    info(f"File: {secrets_file}")

    env = os.environ.copy()
    env['SOPS_AGE_KEY_FILE'] = str(age_key_file)

    sops_config = get_project_root(project) / ".sops.yaml"

    try:
        subprocess.run(
            ["sops", "--config", str(sops_config), str(secrets_file)],
            env=env,
            check=True
        )
        info("Secrets file updated.")
        return True
    except subprocess.CalledProcessError as e:
        error(f"Failed to edit secrets: {e}")
        return False


def decrypt_secrets(output_format: str = "env", key: Optional[str] = None, project: Optional[str] = None) -> bool:
    """Decrypt secrets and output in various formats.

    Args:
        output_format: Output format (env, yaml, json)
        key: Optional specific key to extract
        project: Optional subdirectory name
    """
    secrets_file = get_secrets_path(project)
    age_key_file = get_age_key_path(project)

    if not secrets_file.exists():
        error(f"Encrypted secrets file not found: {secrets_file}")
        click.echo("Run 'ez secrets setup' first", err=True)
        return False

    if not age_key_file.exists():
        error(f"Age key file not found: {age_key_file}")
        click.echo("Run 'ez secrets setup' first", err=True)
        return False

    env = os.environ.copy()
    env['SOPS_AGE_KEY_FILE'] = str(age_key_file)

    sops_config = get_project_root(project) / ".sops.yaml"

    try:
        result = subprocess.run(
            ["sops", "--config", str(sops_config), "--decrypt", str(secrets_file)],
            env=env,
            capture_output=True,
            text=True,
            check=True
        )

        decrypted_content = result.stdout

        if output_format == "yaml":
            click.echo(decrypted_content)
        elif output_format == "json":
            # Convert YAML to JSON using sops
            result = subprocess.run(
                ["sops", "--config", str(sops_config), "--decrypt", "--output-type", "json", str(secrets_file)],
                env=env,
                capture_output=True,
                text=True,
                check=True
            )
            click.echo(result.stdout)
        elif output_format == "env":
            # Parse YAML and output as env vars (simple implementation)
            import yaml
            data = yaml.safe_load(decrypted_content)

            def flatten_dict(d, parent_key='', sep='_'):
                items = []
                for k, v in d.items():
                    new_key = f"{parent_key}{sep}{k}" if parent_key else k
                    if isinstance(v, dict):
                        items.extend(flatten_dict(v, new_key, sep=sep).items())
                    else:
                        items.append((new_key.upper(), v))
                return dict(items)

            if key:
                # Output specific key
                if key in data:
                    click.echo(data[key])
                else:
                    error(f"Key '{key}' not found in secrets")
                    return False
            else:
                # Output all as env vars
                flat_data = flatten_dict(data)
                for k, v in flat_data.items():
                    click.echo(f"export {k}='{v}'")

        return True

    except subprocess.CalledProcessError as e:
        error(f"Failed to decrypt secrets: {e}")
        if e.stderr:
            click.echo(e.stderr, err=True)
        return False
    except Exception as e:
        error(f"Failed to process secrets: {e}")
        return False


def make_temp_secrets_yaml(project: Optional[str] = None) -> bool:
    """Decrypt secrets and write to temporary YAML file with 'secrets:' wrapper.

    Args:
        project: Optional subdirectory name

    Returns:
        True if successful, False otherwise
    """
    secrets_file = get_secrets_path(project)
    age_key_file = get_age_key_path(project)

    if not secrets_file.exists():
        error(f"Encrypted secrets file not found: {secrets_file}")
        click.echo("Run 'ez secrets setup' first", err=True)
        return False

    if not age_key_file.exists():
        error(f"Age key file not found: {age_key_file}")
        click.echo("Run 'ez secrets setup' first", err=True)
        return False

    # Determine output file path
    if project:
        output_file = Path(f"/tmp/{project}-secret-values.yaml")
    else:
        output_file = Path("/tmp/secret-values.yaml")

    env = os.environ.copy()
    env['SOPS_AGE_KEY_FILE'] = str(age_key_file)

    sops_config = get_project_root(project) / ".sops.yaml"

    try:
        # Decrypt secrets
        result = subprocess.run(
            ["sops", "--config", str(sops_config), "--decrypt", str(secrets_file)],
            env=env,
            capture_output=True,
            text=True,
            check=True
        )

        decrypted_content = result.stdout

        # Parse YAML to ensure it's valid
        import yaml
        data = yaml.safe_load(decrypted_content)

        # Write wrapped content to temp file
        with open(output_file, 'w') as f:
            f.write("secrets:\n")
            # Dump the data and indent each line by 4 spaces
            yaml_content = yaml.dump(data, default_flow_style=False, sort_keys=False)
            for line in yaml_content.splitlines():
                f.write(f"    {line}\n")

        info(f"Temporary secrets file created: {output_file}")
        click.echo(f"\nFile location: {output_file}")
        click.echo("\nNote: Remember to delete this file when done:")
        click.echo(f"  rm {output_file}")

        return True

    except subprocess.CalledProcessError as e:
        error(f"Failed to decrypt secrets: {e}")
        if e.stderr:
            click.echo(e.stderr, err=True)
        return False
    except Exception as e:
        error(f"Failed to create temp secrets file: {e}")
        return False
