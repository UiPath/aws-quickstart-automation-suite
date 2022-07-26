#!/bin/bash
set -eu

function main() {
  local try
  local maxtry
  registration_url="$(jq -r ".fixed_rke_address" <"/root/installer/input.json")"
  sed -i "s|127.0.0.1|$registration_url|" /etc/rancher/rke2/rke2.yaml

  try=0
  maxtry=10

  status="notready"
  while [[ "${status}" != "ready" ]] && ((try != maxtry)); do
    echo "Trying to remove node ==== ${try}/${maxtry}"
    try=$((try + 1))
    /root/installer/configureUiPathAS.sh node remove --skip-node-deletion --ignore-missing-zone --ignore-missing-tainted --ignore-lock --name "$(hostname)" && status="ready"
  done

  systemctl stop rke2-server

  try=0

  status="notready"
  while [[ "${status}" != "ready" ]] && ((try != maxtry)); do
    echo "Trying to remove node ==== ${try}/${maxtry}"
    try=$((try + 1))
    /root/installer/configureUiPathAS.sh node remove --ignore-missing-zone --ignore-missing-tainted --ignore-lock --name "$(hostname)" && status="ready"
  done
}

main "$@"
