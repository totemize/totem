#!/usr/bin/env bash
# Fleet entry point. Use Ansible's --limit only for an intentional test subset.
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

exec ansible-playbook playbooks/deploy.yml "${extra_vars[@]}" "$@"
