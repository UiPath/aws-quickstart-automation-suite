#!/bin/bash
set -eux

export PATH=$PATH:/var/lib/rancher/rke2/bin:/root/installer/bin:/usr/local/bin
export KUBECONFIG="/etc/rancher/rke2/rke2.yaml"

function main() {
  local registration_url

  registration_url="$(jq -r ".fixed_rke_address" <"/root/installer/input.json")"

  echo "Installing as Agent"

  registration_status=""
  local try=0
  local maxtry=60

  registration_status=$(curl -w '%{response_code}' -sk -o /dev/null https://"${registration_url}":9345/ping) || true
  while [[ "${registration_status}" != "200" ]] && ((try != maxtry)); do
    try=$((try + 1))
    registration_status=$(curl -w '%{response_code}' -sk -o /dev/null https://"${registration_url}":9345/ping) || true
    echo "Trying to reach ${registration_url} ==== ${try}/${maxtry}" && sleep 30
  done

  sleep 300

  [[ "${registration_status}" == "200" ]] || (echo "Primary server failed to start" && exit 1)
  /root/installer/install-uipath.sh -i /root/installer/input.json -o /root/installer/output.json -k -j agent --accept-license-agreement --skip-pre-reqs --skip-compare-config
}

main "$@"
