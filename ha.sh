#!/usr/bin/env bash

# Temporary HA program until I figure out something better
# Problem is that runner plugin for Flow Launcher cannot
# handle mor ethan 2 parameters, even though "{0}" should
# work. So Thi sis temporary code that will combine 2nd
# and 3rd parameters into one, separated by a dash.
#
# ha.sh litet|litem|liteb|litea|litetb on|off|t-6500|b-100 
#       ac|fan                         on|off
#
# The best solution is to probably build my own plugin


#echo "Arguments:"
#echo "     $1,$2,$3"
#echo "     $@"

param1="$1"
param2="$2"
param3="$3"

# Aliases for devices
if [[ "$1" == "litet" ]]; then
  param1="litetop"
elif [[ "$1" == "litem" ]]; then
  param1="litemiddle"
elif [[ "$1" == "liteb" ]]; then
  param1="litebottom"
elif [[ "$1" == "litea" ]]; then
  param1="litetop,litemiddle,litebottom"
elif [[ "$1" == "litetb" ]]; then
  param1="litetop,litebottom"
fi

# Combine parameters 2 and 3 together, separated by a dash
if [[ "$2" == *"-"* ]]; then
  IFS='-' read -ra parts <<< "$2"
  param2="${parts[0]}"
  param3="${parts[1]}"
fi

echo "Params are now: ${param1}, ${param2}, ${param3}"

# SSH into the pi and run the command
#ssh kupi@cluckcluck.us -p31944 -i "~/.ssh/id_rsa_pi_v2_no_password" ". ~/.env; /usr/local/opt/python-3.8.0/bin/python3.8 ~/home-automation/home_automation.py ${param1} ${param2} ${param3}"

# Run it locally. It runs 2x as fast as the pi. SSH'ing into the pi adds maybe 0.1-0.2 sec on to the pi's time.
python ~/Personal/Code/git/home-automation/home_automation.py ${param1} ${param2} ${param3}

#read -p "Press [Enter] key to start backup..."