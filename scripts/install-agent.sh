#!/bin/bash
set -eux

export PATH=$PATH:/var/lib/rancher/rke2/bin:/root/installer/bin:/usr/local/bin
export KUBECONFIG="/etc/rancher/rke2/rke2.yaml"

NODE_ROLE="agent"

function parse_long_args() {
  while (("$#")); do
    case "$1" in
    
    --node-role)
      if [ -n "$2" ] && [ "${2:0:1}" != "-" ]; then
        NODE_ROLE="$2"
        shift 2
      else
        error "Value for $1 is missing"
        shift 2
      fi
      ;;

    -*) # unsupported flags
      echo "unsupported flag ${1}"
      exit 1
      ;;
    esac
  done
}

function main() {
  local registration_url

  registration_url="$(jq -r ".fixed_rke_address" <"/root/installer/input.json")"

  echo "Installing as ${NODE_ROLE}"

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
  /root/installer/install-uipath.sh -i /root/installer/input.json -o /root/installer/output.json -k -j "${NODE_ROLE}" --accept-license-agreement --skip-compare-config
}

parse_long_args "$@"
main "$@"
