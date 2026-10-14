#!/usr/bin/env bash

# Function to lookup the UID of the user and sub-user combination                                                                          
get_subu_uid() {
  local user=$1
  local subu=$2

  # Concatenate user and sub-user name (no space around the = sign)
  local subu_user="${user}-${subu}"

  # Lookup the UID for the sub-user (user-subuser) combination
  subu_uid=$(id -u "$subu_user" 2>/dev/null)
  
  # If found, return only the UID, otherwise return nothing
  if [ -n "$subu_uid" ]; then
    echo "$subu_uid"
  fi
}

# Call the function with user and subu as arguments                                                                                        
get_subu_uid "$1" "$2"
