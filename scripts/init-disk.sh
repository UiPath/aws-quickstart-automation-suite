#!/bin/bash
set -eu

# positional parameters:
# $1 device name
function mount_ssd_etcd_disk() {
  local disk_dev=$1
  local uuid
  local disk_mount="/var/lib/rancher/rke2/server/db"

  echo "Partitioning ${disk_dev}, creating partition \"data\" with 100%"
  parted "${disk_dev}" --script mklabel gpt mkpart "data" xfs 0% 100%
  # the new partition is not ready for format immediately
  # shellcheck disable=SC2143
  while [[ ! "$(blkid -o device | grep -e "^${disk_dev}1$")" ]]; do
    echo "Waiting for ${disk_dev}1 to be available"
    sleep 5
  done
  init_partition "${disk_dev}1" "${disk_mount}"
}

# positional parameters:
# $1 device name
function mount_ssd_cluster_disk() {
  local disk_dev=$1
  local uuid
  local rancher_mount="/var/lib/rancher"
  local kubelet_mount="/var/lib/kubelet"

  echo "Partitioning ${disk_dev}, creating partitions \"rancher\" and \"kubelet\" with 100%"
  echo "Yes" | parted -a optimal "${disk_dev}" ---pretend-input-tty mklabel gpt
  parted "${disk_dev}" mkpart "rancher" xfs 0% 220G mkpart "kubelet" xfs 220G 100%
  # the new partition is not ready for format immediately
  # shellcheck disable=SC2143
  while [[ ! "$(blkid -o device | grep -e "^${disk_dev}1$")" ]]; do
    echo "Waiting for ${disk_dev}1 to be available"
    sleep 5
  done
  while [[ ! "$(blkid -o device | grep -e "^${disk_dev}2$")" ]]; do
    echo "Waiting for ${disk_dev}2 to be available"
    sleep 5
  done
  init_partition "${disk_dev}1" "${rancher_mount}"
  init_partition "${disk_dev}2" "${kubelet_mount}"
}

# positional parameters:
# $1 partition name
# $2 mount point of the partition
function init_partition() {
  local partition_name
  local partition_mount
  local uuid
  partition_name=$1
  partition_mount=$2
  echo "Creating xfs filesystem for ${partition_name}"
  mkfs.xfs -f "${partition_name}"
  partprobe "${partition_name}"

  echo "Creating mount point ${partition_mount}"
  mkdir -p "${partition_mount}"
  echo "mounting ${partition_name} on ${partition_mount}"
  systemctl daemon-reload
  mount "${partition_name}" "${partition_mount}"
  uuid=$(blkid -o value -s UUID "${partition_name}")
  grep -q "${uuid}" /etc/fstab || printf "# %s\nUUID=%s    %s    xfs    defaults    0    0\n" "${partition_mount}" "${uuid}" "${partition_mount}" >>/etc/fstab
  systemctl daemon-reload
}

# positional parameters:
# $1 device name
function mount_nvme_etcd_disk() {
  local disk_dev=$1
  local uuid
  local disk_mount="/var/lib/rancher/rke2/server/db"

  echo "Partitioning ${disk_dev}, creating partition \"data\" with 100%"
  echo "Yes" | parted -a optimal "${disk_dev}" ---pretend-input-tty mklabel gpt
  parted "${disk_dev}" mkpart "data" xfs 0% 100%
  # the new partition is not ready for format immediately
  # shellcheck disable=SC2143
  while [[ ! "$(blkid -o device | grep -e "^${disk_dev}p1$")" ]]; do
    echo "Waiting for ${disk_dev}p1 to be available"
    sleep 5
  done
  init_partition "${disk_dev}p1" "${disk_mount}"
}

# positional parameters:
# $1 device name
function mount_nvme_cluster_disk() {
  local disk_dev=$1
  local uuid
  local rancher_mount="/var/lib/rancher"
  local kubelet_mount="/var/lib/kubelet"

  echo "Partitioning ${disk_dev}, creating partitions \"rancher\" and \"kubelet\" with 100%"
  echo "Yes" | parted -a optimal "${disk_dev}" ---pretend-input-tty mklabel gpt
  parted "${disk_dev}" mkpart "rancher" xfs 0% 220G mkpart "kubelet" xfs 220G 100%
  # the new partition is not ready for format immediately
  # shellcheck disable=SC2143
  while [[ ! "$(blkid -o device | grep -e "^${disk_dev}p1$")" ]]; do
    echo "Waiting for ${disk_dev}p1 to be available"
    sleep 5
  done
  while [[ ! "$(blkid -o device | grep -e "^${disk_dev}p2$")" ]]; do
    echo "Waiting for ${disk_dev}p2 to be available"
    sleep 5
  done
  init_partition "${disk_dev}p1" "${rancher_mount}"
  init_partition "${disk_dev}p2" "${kubelet_mount}"
}

# positional parameters:
# $1 device name
function mount_nvme_lvm_disk() {
  local disk_dev=$1
  local uuid
  local disk_mount="/datadisk"

  pvcreate -y "${disk_dev}"
  vgcreate datadisk "${disk_dev}"
  lvcreate -n longhorn-datadisk -l 100%VG datadisk -Wy -y

  mkfs.xfs -f /dev/datadisk/longhorn-datadisk
  mkdir -p "${disk_mount}"
  mount /dev/datadisk/longhorn-datadisk "${disk_mount}"

  grep -q "/dev/datadisk/longhorn-datadisk" /etc/fstab || printf "# longhorn-datadisk\n%s    %s    xfs    defaults,nofail    0    0\n" "/dev/datadisk/longhorn-datadisk" "${disk_mount}" >> /etc/fstab
  systemctl daemon-reload
}

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
            mount_nvme_lvm_disk "/dev/nvme${i}n1"
            ;;
            sdc)
            mount_nvme_etcd_disk "/dev/nvme${i}n1"
            ;;
            sdd)
            mount_nvme_cluster_disk "/dev/nvme${i}n1"
            ;;
          esac
          lsblk
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
        mount_ssd_lvm_disk "/dev/xvdb"
        ;;
        xvdc)
        mount_ssd_etcd_disk "/dev/xvdc"
        ;;
        xvdd)
        mount_ssd_cluster_disk "/dev/xvdd"
        ;;
      esac
      lsblk
    fi
  done
fi

mount -a
