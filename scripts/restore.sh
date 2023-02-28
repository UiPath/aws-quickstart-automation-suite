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

echo "Checking snapshot workload rediness..."
try=0
maxTries=5
until /opt/UiPathAutomationSuite/Installer/configureUiPathAS.sh snapshot list | grep -q "$1" || ((try == maxTries)); do
  echo "[$try/$maxTries]Snapshot workload is not ready yet. Checking again in 30 seconds..."
  try=$((try + 1))
  sleep 30s
done

if ! /opt/UiPathAutomationSuite/Installer/configureUiPathAS.sh snapshot list | grep -q "$1"; then
  echo "Maximum retries reached. Snapshot workload is not ready yet. Exiting restore process."
  exit 1
fi

echo "Snapshot workload is ready. Starting restore..."
/root/installer/configureUiPathAS.sh snapshot restore create --from-snapshot "$1"

export KUBECONFIG=/etc/rancher/rke2/rke2.yaml PATH=$PATH:/var/lib/rancher/rke2/bin
kubectl patch gateway main-gateway -p='[{"op":"add", "path":"/spec/servers/0/hosts/-", "value":"*"}]' -n istio-system --type=json
kubectl -n istio-system delete pod --all
echo "Restore finished succesfully."

echo "Disabling maintenance mode..."
/root/installer/configureUiPathAS.sh disable-maintenance-mode
echo "Maintenance mode disabled."