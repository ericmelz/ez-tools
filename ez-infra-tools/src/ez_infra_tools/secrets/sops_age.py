"""SOPS and Age encryption utilities for secrets management."""

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

import click


def get_project_root() -> Path:
    """Get the project root directory."""
    # When installed, look in current working directory
    return Path.cwd()


def get_secrets_dir() -> Path:
    """Get the secrets directory path."""
    return get_project_root() / "secrets"


def get_age_key_path() -> Path:
    """Get the age key file path."""
    return get_secrets_dir() / "age-key.txt"


def get_secrets_path() -> Path:
    """Get the secrets YAML file path."""
    return get_secrets_dir() / "secrets.yaml"


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


def generate_age_key() -> Optional[str]:
    """Generate an age key if it doesn't exist. Returns the public key."""
    age_key_file = get_age_key_path()
    secrets_dir = get_secrets_dir()

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


def create_sops_config(public_key: str) -> bool:
    """Create .sops.yaml configuration file."""
    sops_config_path = get_project_root() / ".sops.yaml"

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


def create_initial_secrets_file() -> bool:
    """Create an initial encrypted secrets file."""
    secrets_file = get_secrets_path()
    age_key_file = get_age_key_path()

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

    secrets_dir = get_secrets_dir()
    secrets_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Write initial content directly to final file
        with open(secrets_file, 'w') as f:
            f.write(initial_content)

        # Encrypt with sops in-place
        env = os.environ.copy()
        env['SOPS_AGE_KEY_FILE'] = str(age_key_file)

        subprocess.run(
            ["sops", "--encrypt", "--in-place", str(secrets_file)],
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


def setup_secrets() -> bool:
    """Complete setup process for secrets management."""
    if not check_dependencies():
        return False

    public_key = generate_age_key()
    if not public_key:
        error("Failed to generate or read age key")
        return False

    if not create_sops_config(public_key):
        return False

    if not create_initial_secrets_file():
        return False

    info("\nSecrets setup complete!")
    info(f"Age key: {get_age_key_path()}")
    info(f"Secrets file: {get_secrets_path()}")
    info(f"SOPS config: {get_project_root() / '.sops.yaml'}")
    click.echo("\nNext steps:", err=True)
    click.echo("  1. Backup your age key to a secure location", err=True)
    click.echo("  2. Edit secrets with: ez secrets edit", err=True)
    click.echo("  3. Decrypt secrets with: ez secrets decrypt", err=True)

    return True


def edit_secrets() -> bool:
    """Edit encrypted secrets file using SOPS."""
    secrets_file = get_secrets_path()
    age_key_file = get_age_key_path()

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

    try:
        subprocess.run(
            ["sops", str(secrets_file)],
            env=env,
            check=True
        )
        info("Secrets file updated.")
        return True
    except subprocess.CalledProcessError as e:
        error(f"Failed to edit secrets: {e}")
        return False


def decrypt_secrets(output_format: str = "env", key: Optional[str] = None) -> bool:
    """Decrypt secrets and output in various formats."""
    secrets_file = get_secrets_path()
    age_key_file = get_age_key_path()

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

    try:
        result = subprocess.run(
            ["sops", "--decrypt", str(secrets_file)],
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
                ["sops", "--decrypt", "--output-type", "json", str(secrets_file)],
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
