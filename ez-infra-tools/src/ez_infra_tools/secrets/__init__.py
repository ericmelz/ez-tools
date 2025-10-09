"""Secrets management module for SOPS and Age encryption."""

from .sops_age import (
    check_dependencies,
    generate_age_key,
    setup_secrets,
    edit_secrets,
    decrypt_secrets,
    make_temp_secrets_yaml,
    get_age_key_path,
    get_secrets_path,
)

__all__ = [
    "check_dependencies",
    "generate_age_key",
    "setup_secrets",
    "edit_secrets",
    "decrypt_secrets",
    "make_temp_secrets_yaml",
    "get_age_key_path",
    "get_secrets_path",
]
