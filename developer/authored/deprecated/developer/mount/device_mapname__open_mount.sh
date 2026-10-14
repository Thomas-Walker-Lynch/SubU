#!/usr/bin/env bash

if [[ $EUID -ne 0 ]]; then
  echo "❌ This script must be run as root." >&2
  exit 1
fi

# Function to unlock and mount the device
device_mount() {
  local device_node=$1   # e.g., /dev/sdb1
  local device_name=$2   # e.g., Zathustra
  local mount_point="/mnt/$device_name"

  # Check if cryptsetup is installed
  if ! command -v cryptsetup &> /dev/null; then
    echo "Error: cryptsetup is not installed!"
    return 1
  fi

  # Check if the device is already mounted
  if mount | grep "on $mount_point" > /dev/null; then
    echo "Device $device_name is already mounted at $mount_point."
    return 0
  fi

  # Make sure the mount point exists
  mkdir -p "$mount_point"

  # Unlock the encrypted device
  sudo cryptsetup luksOpen "$device_node" "$device_name-crypt"

  # Mount the unlocked device
  sudo mount "/dev/mapper/$device_name-crypt" "$mount_point"

  echo "$device_name mounted at $mount_point"
}

# Run the function with the device node and device name as arguments
device_mount "$1" "$2"
