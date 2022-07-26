#!/bin/bash
set -eu

CONFIGURESERVERDISK=0

function parse_long_args() {
  while (("$#")); do
    case "$1" in
    -s | --server)
      CONFIGURESERVERDISK=1
      shift
      ;;

    -*) # unsupported flags
      echo "unsupported flag ${1}"
      exit 1
      ;;
    esac
  done
}

function main() {
  local data_disk
  local cluster_disk
  local etcd_disk
  lsblk
  systemctl daemon-reload
  root_dev=$(lsblk -d | grep "nvme0n1" | awk '{print $1}')
  if [[ -n "${root_dev}" ]]; then
    declare -a dev_arr=("sdb" "sdd" "sdc")
    for crt_dev in "${dev_arr[@]}"; do
      for i in $(seq 26); do
        if [[ -b "/dev/nvme${i}n1" ]]; then
          nvme_dev=""
          nvme_dev=$(/root/ebsnvme-id.py "/dev/nvme${i}n1" -b) || true
          if [[ -n "${nvme_dev}" ]] && [[ "${nvme_dev}" == "${crt_dev}" ]]; then
            echo "NVME device name /dev/nvme${i}n1 mapped to ${crt_dev}"
            case "${crt_dev}" in
              sdb)
              data_disk="/dev/nvme${i}n1"
              ;;
              sdc)
              etcd_disk="/dev/nvme${i}n1"
              ;;
              sdd)
              cluster_disk="/dev/nvme${i}n1"
              ;;
            esac
          fi
        fi
      done
    done
  else
    declare -a dev_arr=("xvdb" "xvdd" "xvdc")
    for crt_dev in "${dev_arr[@]}"; do
      if [[ -b "/dev/${crt_dev}" ]]; then
        echo "SSD device name /dev/${crt_dev} found"
        case "${crt_dev}" in
          xvdb)
          data_disk="/dev/xvdb"
          ;;
          xvdc)
          etcd_disk="/dev/xvdc"
          ;;
          xvdd)
          cluster_disk="/dev/xvdd"
          ;;
        esac
      fi
    done
  fi
  # If the node is an agent there is no need to check for full install
  if ((CONFIGURESERVERDISK == 0)); then
    echo "Configuring disk for agent installation"
    /root/installer/configureUiPathDisks.sh --node-type agent \
                                            --install-type online \
                                            --cluster-disk-name "${cluster_disk}"
  else
    local install_ai_center=$(cat /root/installer/input.json | jq -r '.aicenter.enabled')
    local install_task_mining=$(cat /root/installer/input.json | jq -r '.task_mining.enabled')
    local install_du=$(cat /root/installer/input.json | jq -r '.documentunderstanding.enabled')
    local install_apps=$(cat /root/installer/input.json | jq -r '.enabled.enabled')
    if [[ "${install_ai_center}" == "true" || "${install_task_mining}"  == "true" || "${install_du}"  == "true" || "${install_apps}"  == "true" ]]; then
      echo "Configuring disk for server complete installation"
      /root/installer/configureUiPathDisks.sh --node-type server \
                                              --install-type online \
                                              --cluster-disk-name "${cluster_disk}" \
                                              --etcd-disk-name "${etcd_disk}" \
                                              --data-disk-name "${data_disk}" \
                                              --complete-suite
    else
      echo "Configuring disk for server default installation"
      /root/installer/configureUiPathDisks.sh --node-type server \
                                              --install-type online \
                                              --cluster-disk-name "${cluster_disk}" \
                                              --etcd-disk-name "${etcd_disk}" \
                                              --data-disk-name "${data_disk}"
    fi
  fi
  lsblk
  mount -a
}

parse_long_args "$@"
main