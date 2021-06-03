"""
  Home automation scripts for Wyze devices
  by Brian Kummer, June 2021

  This script expects the following environmental variables to be set
    WYZE_EMAIL="xxxxx@gmail.com"
    WYZE_PASSWORD="xxxxxxxx"
    WYZE_DEVICE_FAN="plug|xxxxxxxxxxxx"
    WYZE_DEVICE_AC="plug|xxxxxxxxxxxx"
"""
import sys
import os
from wyze_sdk import Client
from wyze_sdk.errors import WyzeApiError

client = Client(email=os.environ.get('WYZE_EMAIL'), password=os.environ.get('WYZE_PASSWORD'))


"""
  Validate a device name and parse the device's type and MAC address from
  its environmental variable

  Inputs:
    * The device's name (i.e. "fan")

  Outputs:
    * An error message if the device name is invalid

  Returns:
    * Is the device's name valid?
    * The device's type
    * The device's MAC address
"""
def validate_device(device_name): 
  device_env_variable = f"WYZE_DEVICE_{device_name.upper()}"
  device_info = os.environ.get(device_env_variable)
  if device_info:
    device_parts = device_info.split("|")
    return True, device_parts[0], device_parts[1]
  else:
    print(f"Device {device_name} doesn't exist- set environment variable {device_env_variable}")
    return False, "", ""


"""
  Validate the action

  Inputs:
    * The action name (i.e. "on")

  Outputs:
    * An error message if the action is invalid

  Returns:
    * Is the action valid?
"""
def validate_action(action):
  if action != "on" and action != "off":
    print(f"Invalid action")
    return False
  else:
    return True


"""
  Validate the command-line parameters

  Inputs:
    * The device's name (i.e. "fan")
    * The action to perform on that device (i.e. "on")

  Outputs:
    * Syntax help if 2 parameters are not passed
    * Error message(s) if the device name and/or action are invalid

  Returns:
    * Are all the parameters valid?
    * The device's type
    * The device's MAC address
    * The action to perform on the device
"""
def validate_parameters(params):
  device_type = device_mac = action = ""
  is_valid_device_name = is_valid_action = False

  if len(params) != 3:
    print(f"Syntax:")
    print(f"    wyze.py <device_name> <action>")
    print(f"        device_name: fan|ac")
    print(f"        action:      on|off")
  else:
    device_name = params[1].lower()
    action = params[2].lower()

    is_valid_device_name, device_type, device_mac = validate_device(device_name)
    is_valid_action = validate_action(action)

  return is_valid_device_name and is_valid_action, device_type, device_mac, action


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
  if action == "off":
    client.plugs.turn_off(device_mac=plug.mac, device_model=plug.product.model)
  else:
    client.plugs.turn_on(device_mac=plug.mac, device_model=plug.product.model)


"""
  Perform an action on a light bulb

  Inputs:
    * The device's MAC address
    * The action to perform on the device

  Outputs:
    * Turns the bulb on or off
"""
def bulb_action():
  #TODO: duh!
  pass


"""
  Main body
"""
try:
  is_valid = False
  device_type = device_mac = action = ""
  is_valid, device_type, device_mac, action = validate_parameters(sys.argv)
  if is_valid:
    device_actions = {
      "plug": plug_action,
      "bulb": bulb_action
    }
    device_actions[device_type](device_mac, action)

except WyzeApiError as e:
    # You will get a WyzeApiError if the request failed
    print(f"Got an error: {e}")