#!/bin/bash
set -eu

export PATH=$PATH:/var/lib/rancher/rke2/bin:/root/installer/bin:/usr/local/bin
export KUBECONFIG="/etc/rancher/rke2/rke2.yaml"

SETUPBACKUP=0

function get_first_server() {
  local instance_id
  local metadata_token
  metadata_token=$(curl -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 300")
  instance_id=$(curl -H "X-aws-ec2-metadata-token: $metadata_token" -s http://169.254.169.254/latest/meta-data/instance-id)
  echo "Local instance id: ${instance_id}"
  asg_name=$(aws autoscaling describe-auto-scaling-instances --instance-ids "${instance_id}" --query 'AutoScalingInstances[*].AutoScalingGroupName' --output text)
  instances=$(aws autoscaling describe-auto-scaling-groups --auto-scaling-group-name "$asg_name" --query 'AutoScalingGroups[*].Instances[?HealthStatus==`Healthy`].InstanceId' --output text)

  echo "Instances in the autoscaling group: ${instances}"

  sorted_instances=$(echo "${instances}" | tr ' ' '\n' | sort | tr '\n' ' ')
  read -r -a arr_sorted_instances <<<"$sorted_instances"
  first_server=$(echo "${instances}" | tr ' ' '\n' | sort | tr '\n' ' ' | awk '{print $1}')

  LOCATION_IN_ARRAY=0
  for crt_instance in "${arr_sorted_instances[@]}"; do
    [[ $crt_instance == "$instance_id" ]] && { echo "$LOCATION_IN_ARRAY"; break; }
    ((++LOCATION_IN_ARRAY))
  done
  LOCATION_IN_ARRAY=$((LOCATION_IN_ARRAY - 1))

  echo "Current instance: ${instance_id} | First server instance: ${first_server} | Current location in array: ${LOCATION_IN_ARRAY}"

  if [[ "${instance_id}" == "$first_server" ]]; then
    echo "Current node is the first server"
    NODE_TYPE="FIRST_SERVER"
  else
    echo "Current node is a secondary server"
    NODE_TYPE="SECONDARY_SERVER"
  fi
}

function parse_long_args() {
  while (("$#")); do
    case "$1" in
    -b | --backup)
      SETUPBACKUP=1
      shift
      ;;

    -*) # unsupported flags
      echo "unsupported flag ${1}"
      exit 1
      ;;
    esac
  done
}

function check_registration() {
  local registration_url=$1
  local registration_status

  registration_status=""
  local try=0
  local maxtry=5

  while [[ "${registration_status}" != "200" ]] && ((try != maxtry)); do
    try=$((try + 1))
    registration_status=$(curl -m 5 -w '%{response_code}' -sk -o /dev/null https://"${registration_url}":9345/ping) || true
    echo "Trying to reach ${registration_url} ==== ${try}/${maxtry}" && sleep 2
  done

  if [[ "${registration_status}" -ne "200" ]]; then
    echo "No RKE2 server listening at the registration address"
    get_first_server
  else
    echo "There is already an RKE2 server listening at the registration address"
    NODE_TYPE="SECONDARY_SERVER"
  fi
}

function main() {
  NODE_TYPE="FIRST_SERVER"
  local registration_url
  local no_of_nodes_actual
  local no_of_nodes_required
  export LOCATION_IN_ARRAY=0

  registration_url="$(jq -r ".fixed_rke_address" <"/root/installer/input.json")"

  check_registration "${registration_url}"

  if [[ "${NODE_TYPE}" == "FIRST_SERVER" ]]; then
    echo "Installing as primary server"

    echo "Generating certificates for first installation"
    /root/installer/generate-certs.sh

    try=0
    maxtry=2

    status="notready"
    while [[ "${status}" != "ready" ]] && ((try != maxtry)); do
      echo "Trying to install the infra ==== ${try}/${maxtry}"
      try=$((try + 1))
      /root/installer/install-uipath.sh -i /root/installer/input.json -o /root/installer/output.json -k --accept-license-agreement --skip-pre-reqs --skip-compare-config && status="ready"
    done

    [[ "${status}" == "ready" ]] || (echo "Failed to install infra" && exit 1)

    kubectl patch gateway main-gateway -p='[{"op":"add", "path":"/spec/servers/0/hosts/-", "value":"*"}]' -n istio-system --type=json
    kubectl -n istio-system delete pod --all
    /root/upload-kubeconfig.sh

    echo "waiting for the other nodes"
    no_of_nodes_required="$(jq -r ".initial_number_of_instances" <"/root/installer/input.json")"
    nodereadypath='{range .items[*]}{@.metadata.name}:{range @.status.conditions[*]}{@.type}={@.status}{end}{"\n"}{end}'

    local try=0
    local maxtry=60
    no_of_nodes_actual=$(kubectl get nodes -o jsonpath="$nodereadypath" | grep -c -E "Ready=True")

    while ((no_of_nodes_actual < no_of_nodes_required)) && ((try != maxtry)); do
      try=$((try + 1))
      echo "Waiting for ${no_of_nodes_required} to be ready, current nodes ${no_of_nodes_actual} ==== ${try}/${maxtry}" && sleep 30
      no_of_nodes_actual=$(kubectl get nodes -o jsonpath="$nodereadypath" | grep -c -E "Ready=True")
    done

    ((no_of_nodes_actual >= no_of_nodes_required)) || (echo "Required number of nodes failed to start" && exit 1)

    try=0
    maxtry=2

    status="notready"
    while [[ "${status}" != "ready" ]] && ((try != maxtry)); do
      echo "Trying to install the fabric ==== ${try}/${maxtry}"
      try=$((try + 1))
      /root/installer/install-uipath.sh -i /root/installer/input.json -o /root/installer/output.json -f --accept-license-agreement --skip-pre-reqs --skip-compare-config && status="ready"
    done

    [[ "${status}" == "ready" ]] || (echo "Failed to install fabric" && exit 1)
    try=0
    maxtry=2

    status="notready"
    while [[ "${status}" != "ready" ]] && ((try != maxtry)); do
      echo "Trying to install the services ==== ${try}/${maxtry}"
      try=$((try + 1))
      /root/installer/install-uipath.sh -i /root/installer/input.json -o /root/installer/output.json -s --accept-license-agreement --skip-pre-reqs --skip-compare-config && status="ready"
    done
    [[ "${status}" == "ready" ]] || (echo "Failed to install services" && exit 1)

    if ((SETUPBACKUP == 1)); then
      try=0
      maxtry=2

      status="notready"
      while [[ "${status}" != "ready" ]] && ((try != maxtry)); do
        echo "Trying to enable backup ==== ${try}/${maxtry}"
        try=$((try + 1))
        /root/installer/install-uipath.sh -i /root/installer/backup.json -o /root/installer/output-backup.json -b --accept-license-agreement && status="ready"
      done
      [[ "${status}" == "ready" ]] || (echo "Failed to enable backup" && exit 1)
    fi

  else
    echo "Installing as secondary server"

    registration_status=""
    local try=0
    local maxtry=60

    registration_status=$(curl -w '%{response_code}' -sk -o /dev/null https://"${registration_url}":9345/ping) || true
    while [[ "${registration_status}" != "200" ]] && ((try != maxtry)); do
      try=$((try + 1))
      registration_status=$(curl -w '%{response_code}' -sk -o /dev/null https://"${registration_url}":9345/ping) || true
      echo "Trying to reach ${registration_url} ==== ${try}/${maxtry}" && sleep 30
    done

    [[ "${registration_status}" == "200" ]] || (echo "Primary server failed to start" && exit 1)

    echo "Primary server is up. Position in array of current server is: ${LOCATION_IN_ARRAY}"
    # waiting for Longhorn and Istio to install on primary server
    echo "sleeping 7 minutes"
    sleep 420
    # introducing 5 minutes between servers, to avoid the etcd too many learners race condition
    sleep $((LOCATION_IN_ARRAY * 300))

    status="success"
    /root/installer/install-uipath.sh -i /root/installer/input.json -o /root/installer/output.json -k -j server --accept-license-agreement --skip-pre-reqs || status="failed"
    if [[ "${status}" == "failed" ]]; then
      echo "The RKE2 server failed to start"
      exit 1
    fi
    if ((SETUPBACKUP == 1)); then
      /root/installer/install-uipath.sh -i /root/installer/backup.json -o /root/installer/output-backup.json -b -j server --accept-license-agreement
    fi
  fi

  try=0
  maxtry=10

  while [[ $(kubectl get --raw='/readyz') != "ok" ]] && ((try != maxtry)); do
    try=$((try + 1))
    echo "waiting for kubernetes api server to be ready...${try}/${maxtry}" &&  sleep 10;
  done

  try=0
  while [[ $(kubectl get node "$(hostname)" -o 'jsonpath={..status.conditions[?(@.type=="Ready")].status}') =~ "False" ]] && ((try != maxtry)); do
    try=$((try + 1))
    echo "waiting for server to be ready...${try}/${maxtry}" &&  sleep 10;
  done

  kubectl cluster-info &>/dev/null || (echo "Could not reach the cluster API" && exit 1)
}

parse_long_args "$@"
main "$@"
