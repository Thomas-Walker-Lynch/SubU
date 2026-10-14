#!/usr/bin/env bash

# Function to list users in the /mnt/<device>/user_data directory
device_user_list() {
  local device=$1
  local user_data_dir="/mnt/$device/user_data"

  if [ ! -d "$user_data_dir" ]; then
    echo "Error: $user_data_dir does not exist!"
    return 1
  fi

  # List all user directories in the user_data directory
  find "$user_data_dir" -maxdepth 1 -mindepth 1 -type d -exec basename {} \;
}

# Run the function with the device name as an argument
device_user_list "$1"
