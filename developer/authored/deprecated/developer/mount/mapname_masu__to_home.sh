#!/usr/bin/env bash

# Function to bind mount a user's data to /home/<user>
device_user_bind() {
  local device=$1
  local user=$2
  local user_data_dir="/mnt/$device/user_data/$user"
  local home_dir="/home/$user"

  if [ ! -d "$user_data_dir" ]; then
    echo "Error: $user_data_dir does not exist!"
    return 1
  fi

  # Create the home directory if it doesn't exist
  mkdir -p "$home_dir"

  # Mount --bind the user data to the home directory
  sudo mount --bind "$user_data_dir" "$home_dir"
  echo "Mounted $user_data_dir -> $home_dir"
}

# Run the function with the device name and user as arguments
device_user_bind "$1" "$2"
