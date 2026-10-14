#!/usr/bin/env bash

# Function to bind mount with UID/GID mapping
subu_bind() {
  local user=$1
  local subu=$2

  # Check if bindfs is installed
  if ! command -v bindfs &> /dev/null; then
    echo "Error: bindfs is not installed!"
    return 1
  fi

  # Get the username and group name for the main user
  master_user_name=$user
  master_group=$user

  # Get the username and group name for the sub-user
  subu_user_name="${user}-${subu}"
  subu_group="${user}-${subu}"

  # Check if the user and sub-user exist
  if ! id "$master_user_name" &>/dev/null; then
    echo "Error: User '$master_user_name' not found!"
    return 1
  fi
  if ! id "$subu_user_name" &>/dev/null; then
    echo "Error: Sub-user '${master_user_name}-${subu}' not found!"
    return 1
  fi

  # Directories to be bind-mounted
  subu_data_path="/home/$user/subu_data/$subu"
  subu_mount_point_path="/home/$user/subu/$subu"

  # Check if sub-user directory exists
  if [ ! -d "$subu_data_path" ]; then
    echo "Error: Sub-user directory '$subu_data_path' does not exist!"
    return 1
  fi

  # Create the mount point if it doesn't exist
  mkdir -p "$subu_mount_point_path"

  # Perform the bind mount using bindfs with UID/GID mapping
  sudo bindfs\
       --map="$subu_user_name/$master_user_name:@$subu_group/@$master_group" \
       "$subu_data_path" \
       "$subu_mount_point_path"

  # Verify if the mount was successful
  if [ $? -eq 0 ]; then
    echo "Successfully bind-mounted $subu_data_path to $subu_mount_point_path with UID/GID mapping."
  else
    echo "Error: Failed to bind-mount $subu_data_path to $subu_mount_point_path, might already exist."
  fi
}

# Call the function with user and subu as arguments
subu_bind "$1" "$2"
