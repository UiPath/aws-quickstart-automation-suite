#!/bin/bash
set -eux

export PATH=$PATH:/var/lib/rancher/rke2/bin:/root/installer/bin:/usr/local/bin
export KUBECONFIG="/etc/rancher/rke2/rke2.yaml"

function signal_resources() {
  /opt/uipath/signal-resource.sh $?
}

function install_agent() {
  local registration_url

  registration_url="$(jq -r ".fixed_rke_address" <"/root/installer/input.json")"

  echo "Installing as GPU enabled node"

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
  /root/installer/install-uipath.sh -i /root/installer/input.json -o /root/installer/output.json -k -j gpu --accept-license-agreement
}

function main() {
  if [[ -f /opt/uipath/installed ]]; then
    echo "GPU drivers installed already; skipping ..."
  else
    echo "Installing GPU drivers ..."
    yum install -y https://dl.fedoraproject.org/pub/epel/epel-release-latest-8.noarch.rpm
    sed 's/$releasever/8/g' -i /etc/yum.repos.d/epel.repo
    sed 's/$releasever/8/g' -i /etc/yum.repos.d/epel-modular.repo
    yum config-manager --add-repo http://developer.download.nvidia.com/compute/cuda/repos/rhel8/x86_64/cuda-rhel8.repo
    yum install -y cuda

    distribution=$(
      . /etc/os-release
      echo $ID$VERSION_ID
    ) && curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.repo | sudo tee /etc/yum.repos.d/nvidia-docker.repo
    dnf clean expire-cache
    yum install -y nvidia-container-runtime.x86_64
    touch /opt/uipath/installed
    install_agent
  fi

}

trap "signal_resources" EXIT
main "$@"
