#!/usr/bin/env bash
# Sprint-safe entry point: this wrapper can only target inventory host metot.
set -euo pipefail

script_dir=$(cd "$(dirname "$0")" && pwd)
ansible_root=$(cd "$script_dir/.." && pwd)
cd "$ansible_root"

extra_vars=()
if [[ -n "${TOTEM_SSH_PASSWORD:-}" ]]; then
  extra_vars+=(
    --extra-vars "ansible_password=$TOTEM_SSH_PASSWORD"
    --extra-vars "ansible_become_password=$TOTEM_SSH_PASSWORD"
  )
fi

exec ansible-playbook playbooks/deploy.yml --limit metot "${extra_vars[@]}" "$@"
