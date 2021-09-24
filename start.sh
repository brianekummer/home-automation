#!/usr/bin/env bash
#
# start.sh
#
# This isn't pretty- improve it later
#
# 1. Set Slack status of all my accounts to auto
# 2. turn on air cleaner, top and bottom lights

echo "TOKENS: ${SLACK_TOKENS}"
IFS='|' read -ra ADDR <<< "${SLACK_TOKENS}"
for slack_token in "${ADDR[@]}"; do
  curl -v -H "Authorization: Bearer ${slack_token}" https://slack.com/api/users.setPresence?presence=auto
done
   
devices="ac,litetop,litebottom"
ssh kupi@cluckcluck.us -p31944 -i "~/.ssh/id_rsa_pi_v2_no_password" ". ~/.env; /usr/local/opt/python-3.8.0/bin/python3.8 ~/home-automation/home_automation.py ${devices} on"

#read -p "Press Enter to end"