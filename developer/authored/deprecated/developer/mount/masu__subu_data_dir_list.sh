#!/usr/bin/env bash

# Function to list sub-users in /home/<user>/subu_data
subu_home_dir_list() {
  local user=$1
  local subu_home_dir="/home/$user/subu_data"

  if [ ! -d "/home/$user" ]; then
    echo "Error: /home/$user does not exist!"
    return 1
  fi

  if [ ! -d "$subu_home_dir" ]; then
    echo "Error: $subu_home_dir does not exist!"
    return 1
  fi

  # List all sub-users in the subu directory
  find "$subu_home_dir" -maxdepth 1 -mindepth 1 -type d -exec basename {} \;
}

# Run the function with the user as an argument
subu_home_dir_list "$1"
