#!/bin/bash
set -eu

export KUBECONFIG="/root/kubeconfig.yaml"
export PATH=$PATH:/var/lib/rancher/rke2/bin:/usr/local/bin

function main() {
  /root/download-kubeconfig.sh
  kubectl cordon "$(hostname)"
  kubectl drain "$(hostname)" --delete-emptydir-data --force=true --grace-period=-1 --ignore-daemonsets=true --skip-wait-for-delete-timeout=300 --timeout=120s
  systemctl stop rke2-agent
  kubectl delete node "$(hostname)"
#  /root/installer/configureUiPathAS.sh node remove --skip-node-deletion --nodes $(hostname)
}

main "$@"
