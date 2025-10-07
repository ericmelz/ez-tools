# EZ Infrastructure Tools

Modern infrastructure management CLI built with Python, providing tools for:

- **Secrets Management** - SOPS and Age integration
- **Kubernetes** - Context management
- **Helm** - Deployment management
- **Nginx** - Configuration updates and deployment

## Prerequisites

- Python 3.13+
- [uv](https://github.com/astral-sh/uv) - Fast Python package manager

## Installation

### For Development

Clone the repository and install with uv:

```bash
cd ez-infra-tools
uv sync
```

### System-wide Installation

Install the package globally using uv:

```bash
uv tool install .
```

To update the global installation after making changes:

```bash
find . -type d -name __pycache__ -exec rm -rf {} +
uv tool install --force --reinstall .
```

Or with pip:

```bash
pip install .
```

## Usage

### Running with uv (Development)

```bash
# Show help
uv run ez --help

# Show version
uv run ez --version

# Run hello world command
uv run ez hello

# Run hello with custom name
uv run ez hello --name "Your Name"

# View available command groups
uv run ez secrets --help
uv run ez k8s --help
uv run ez helm --help
uv run ez nginx --help
```

### Running after system-wide installation

Once installed globally, you can run the CLI from anywhere:

```bash
# Show help
ez --help

# Run commands
ez hello
ez secrets info
ez k8s info
ez helm info
ez nginx info
```

## Project Structure

```
ez-infra-tools/
├── src/
│   └── ez_infra_tools/
│       ├── __init__.py       # Package initialization
│       └── cli.py            # CLI commands and groups
├── pyproject.toml            # Project configuration
└── README.md                 # This file
```

## Development

The project uses:
- **uv** for fast dependency management
- **Click** for building the CLI interface
- **Python 3.13+** for modern Python features

### Adding New Commands

Commands are organized into groups in `src/ez_infra_tools/cli.py`:

1. **secrets** - For SOPS/Age operations
2. **k8s** - For Kubernetes context management
3. **helm** - For Helm deployments
4. **nginx** - For Nginx configuration

Add new commands to the appropriate group or create new groups as needed.

## Roadmap

- [ ] Implement secrets management with SOPS and Age
- [ ] Implement K8s context switching and management
- [ ] Implement Helm deployment automation
- [ ] Implement Nginx configuration management
- [ ] Add comprehensive error handling
- [ ] Add configuration file support
- [ ] Add tests
- [ ] Add CI/CD pipeline

## License

TBD
