#!/bin/bash
export HOME=/root
set -e

if [[ -z $1 ]]; then
  echo "[ERROR] Snapshot name not recieved."
fi
echo "Configuring snapshot workload..."
backup_file="/root/installer/backup.json"
backup_target="$(jq -r '.target' $backup_file)"
backup_endpoint="$(jq -r '.endpoint' $backup_file)"
backup_location="$(jq -r '.location' $backup_file)"
backup_prefix="$(jq -r '.prefix' $backup_file)"
backup_schedule="$(jq -r '.schedule' $backup_file)"
backup_retention="$(jq -r '.retention' $backup_file)"

/root/installer/configureUiPathAS.sh snapshot config --target "$backup_target" \
                                                     --endpoint "$backup_endpoint" \
                                                     --location "$backup_location" \
                                                     --prefix "$backup_prefix" \
                                                     --schedule "$backup_schedule" \
                                                     --retention "$backup_retention"
echo "Snapshot workload configured."

export KUBECONFIG=/etc/rancher/rke2/rke2.yaml PATH=$PATH:/var/lib/rancher/rke2/bin
kubectl patch gateway main-gateway -p='[{"op":"add", "path":"/spec/servers/0/hosts/-", "value":"*"}]' -n istio-system --type=json
kubectl -n istio-system delete pod --all

/root/installer/configureUiPathAS.sh snapshot restore create --from-snapshot "$1"

echo "Disabling maintenance mode..."
/root/installer/configureUiPathAS.sh disable-maintenance-mode
echo "Maintenance mode disabled."