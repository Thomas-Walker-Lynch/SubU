#!/usr/bin/env bash

# Function to list available devices under /mnt, excluding /mnt itself
mount_pt_list() {
  # List all directories in /mnt that are potentially available for mounting
  find /mnt -mindepth 1 -maxdepth 1 -type d -exec basename {} \;
}

# Call the function to display available devices
mount_pt_list
