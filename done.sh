#!/usr/bin/env bash
#
# done.sh
#
# This isn't pretty- improve it later
#
# 1. Set Slack status of all my accounts to away
# 2. Turn off all devices
# 3. Put the computer to sleep

echo "TOKENS: ${SLACK_TOKENS}"
IFS='|' read -ra ADDR <<< "${SLACK_TOKENS}"
for slack_token in "${ADDR[@]}"; do
  curl -v -H "Authorization: Bearer ${slack_token}" https://slack.com/api/users.setPresence?presence=away
done

sleep 30    # Give myself time to get out of the room

devices="ac,fan,litetop,litemiddle,litebottom"
ssh kupi@cluckcluck.us -p31944 -i "~/.ssh/id_rsa_pi_v2_no_password" ". ~/.env; /usr/local/opt/python-3.8.0/bin/python3.8 ~/home-automation/home_automation.py ${devices} off"

rundll32.exe powrprof.dll,SetSuspendState 0,1,0

#read -p "Press Enter to end"