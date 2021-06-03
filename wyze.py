"""
  Home automation script for Wyze devices
  by Brian Kummer, June 2021
  Uses this unofficial API: https://pypi.org/project/wyze-sdk/

  Syntax:
    wyze.py <device-name> <action> <action-value>

    wyze.py <plug-name>   on|off

    wyze.py <bulb-name>   on|off
                          bright   <brightness>
                          temp     <color-temperature>

    Examples:
      wyze.py fan on
      wyze.py ac off
      wyze.py desklite on
      wyze.py desklite bright 100
      wyze.py desklite bright +
      wyze.py desklite temp 3800

  Assumptions:
    * This script expects the following environmental variables to be set
        - For authentication, which requires 2FA on my Wyze account to be
          disabled
            WYZE_EMAIL="xxxxx@gmail.com"
            WYZE_PASSWORD="xxxxxxxx"
        - Each device needs to have an environmental variable (set in 
          ~/.env) with its type and MAC address, like these:
            WYZE_DEVICE_FAN="plug|ABABABABABAB"
            WYZE_DEVICE_AC="plug|121212121212"

  Notes:
    * Authenticating every time I call this script is unnecessarily slow,
      so I cache the authenticated client and read it from disk instead of
      regenerating it every time I run this script.
"""


import sys
import os
import pickle
from wyze_sdk import Client
from wyze_sdk.errors import WyzeApiError
from os import path

WYZE_CLIENT_FILENAME = 'wyze_client.txt'


"""
  Create the Wyze authenticated client. Read it from cache
  if it exists.

  Returns:
    * The authenticated client
"""
def create_wyze_client():
  client = ""
  if path.exists(WYZE_CLIENT_FILENAME):
    new_file = open(WYZE_CLIENT_FILENAME, 'rb')
    client = pickle.load(new_file)
  else:
    client = Client(email=os.environ.get('WYZE_EMAIL'), password=os.environ.get('WYZE_PASSWORD'))
    file = open(WYZE_CLIENT_FILENAME, 'wb')
    pickle.dump(client, file)
    file.close()
  return client


"""
  Parse the script's parameters into a device_type, device_mac, action,
  and action_value. The device's name is used to find the environment
  variable that contains the device's type and MAC address.

  Inputs:
    * Parameters passed into the script
    * Environment variables named WYZE_DEVICE_xxxx that define
      the device type and MAC address for the device

  Returns:
    * The device's type (plug|bulb)
    * The device's MAC address
    * The action
    * The action_value (brightness, color temperature)
"""
def parse_parameters(params):
  device_name = params[1].lower() if len(params) > 1 else None
  action = params[2].lower() if len(params) > 2 else None
  action_value = params[3].lower() if len(params) > 3 else None

  if device_name:
    device_env_variable = f"WYZE_DEVICE_{device_name.upper()}"
    device_info = os.environ.get(device_env_variable)
    if device_info:
      device_parts = device_info.split('|')
      return device_parts[0], device_parts[1], action, action_value
    else:
      print(f"Device {device_name} isn't defined- set environment variable {device_env_variable}\n")
  else:
    print(f"device-name is a required field\n")

  return None, None, None, None


"""
  Validate the action value

  Inputs:
    * Action value type (None|brightness|color-remperature)
    * Action value to validate

  Returns:
    * Is it valid?
"""
def validate_action_value(action_value_type, action_value):
  is_valid = False

  if action_value_type == None:
    is_valid = True

  elif action_value_type == "brightness":
    if action_value == None:
      print(f"action-value is a required field\n")
    elif (action_value.isnumeric() and 0 <= action_value <= 100) or action_value in {'+', '-'}:
      is_valid = True
    else:
      print(f"{action_value} is not a valid brightness value\n")

  elif action_value_type == "color-temperature":
    if action_value == None:
      print(f"action-value is a required field\n")
    elif action_value.isnumeric() or action_value in {'+', '-'}:
      is_valid = True
    else:
      print(f"{action_value} is not a valid color temperature value\n")
      
  else:
    print(f"{action_value_type} is an invalid action value type\n")
  
  return is_valid


"""
  Validate the parameters. Ensures that we don't try to set the brightness
  on a smart plug.

  Inputs:
    * The device's type
    * The action
    * The action's value
"""
def validate_parameters(device_type, action, action_value):
  validations = {
    'plug': { 'on':     None,
              'off':    None }, 
    'bulb': { 'on':     None,
              'off':    None,
              'bright': 'brightness',
              'temp':   'color-temperature' }
  }

  is_valid = False
  if device_type in validations:
    if action in validations[device_type]:
      action_value_type = validations[device_type][action]
      is_valid = validate_action_value(action_value_type, action_value)
    else:
      if action == None:
        print('action is a required field\n')
      else:
        print(f"{action} is not a valid action\n")
  elif device_type != None:
    print(f"{device_type} is not a valid device type\n")

  return is_valid


"""
  Perform an action on a plug

  Inputs:
    * The device's MAC address
    * The action to perform on the device

  Outputs:
    * Turns the plug on or off
"""
def plug_action(device_mac, action):
  plug = client.plugs.info(device_mac=device_mac)
  if action == 'off':
    client.plugs.turn_off(device_mac=plug.mac, device_model=plug.product.model)
  elif action == 'on':
    client.plugs.turn_on(device_mac=plug.mac, device_model=plug.product.model)


"""
  Perform an action on a light bulb

  Inputs:
    * The device's MAC address
    * The action to perform on the device
    * The value for the action (brightness or color temperature)

  Outputs:
    * Turns the bulb on or off
      OR
    * Sets the bulb's brightness
      OR
    * Sets the bulb's color temperature
"""
def bulb_action(device_mac, action, action_value):
  bulb = client.bulbs.info(device_mac=device_mac)
  if action == 'off':
    client.bulbs.turn_off(device_mac=bulb.mac, device_model=bulb.product.model)
  elif action == 'on':
    client.bulbs.turn_on(device_mac=bulb.mac, device_model=bulb.product.model)
  elif action == 'bright':
    client.bulbs.set_brightness(device_mac=bulb.mac, device_model=bulb.product.model, brightness=action_value)
  elif action == 'temp':
    client.bulbs.set_color_temp(device_mac=bulb.mac, device_model=bulb.product.model, color_temp=action_value)


"""
  Main body 
"""
try:
  is_valid = False
  device_type, device_mac, action, action_value = parse_parameters(sys.argv)
  is_valid = validate_parameters(device_type, action, action_value)
  if not is_valid:
    print('Syntax:')
    print('  wyze.py <device_name> <action> <action-value>')
    print('    device_name:  fan|ac|desklite')
    print('    action:       on|off|bright|temp')
    print('    action-value: brightness or color temperature ')
    print('')
    print('  For plugs, valid actions are on|off')
    print('  For bulbs, valid actions are on|off|bright|temp')
    print('    actions of bright|temp require action_value, is either a number or +/-')
    print('')
    print('Examples:')
    print('  wyze.py fan on')
    print('  wyze.py ac off')
    print('  wyze.py desklite on')
    print('  wyze.py desklite bright 100')
    print('  wyze.py desklite bright +')
    print('  wyze.py desklite temp 3800')
  else:
    client = create_wyze_client()
    if device_type == 'plug':
      plug_action(device_mac, action)
    elif device_type == 'bulb':
      bulb_action(device_mac, action, action_value)

except WyzeApiError as e:
    # You will get a WyzeApiError if the request failed
    print(f"Got an error: {e}")