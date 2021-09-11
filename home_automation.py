"""
  Home automation script
  by Brian Kummer, Sept 2021
  
  Supports Wyze and VeSync (which includes Levoit) devices using unofficial API's
    - https://pypi.org/project/wyze-sdk/ requires Python 3.8 or higher
    - https://github.com/webdjoe/pyvesync

  Syntax:
    home_automation.py <device-names> <action> <action-value>
      (see main body for details and examples)

  Assumptions:
    * This script expects the following environment variables to be set
        - For authentication, which requires 2FA on my Wyze account to be
          disabled
            HA_EMAIL="xxxxx@gmail.com"
            HA_WYZE_PASSWORD="xxxxxxxx"
            HA_VESYNC_PASSWORD="xxxxx"
        - Each device needs to have an environment variable (set in 
          ~/.env) with its api, type, and id, like these:
            HA_DEVICE_FAN="wyze|plug|ABABABABABAB"
            HA_DEVICE_LITE="wyze|bulb|121212121212"
            HA_DEVICE_AC="vesync|fan|xxxxxxx"
    * Device types are not shared between APIs. For example, I do not have
      a Wyze plug and a VeSync plug

  Notes:
    * Authenticating every time I call this script is unnecessarily slow,
      so I cache the authenticated client and read it from disk instead of
      regenerating it every time I run this script.

  TO DO - LATER - Changes for Color/Mesh Bulbs
    * Refactor to clean up code
        - Move some/all of the device validation (validate_action_value) into 
          wyze/vesync code because it's specific to each api
        - Consider making home_automation_wyze and home_automation_vesync classes?
        - Combine api + device_type somehow so that this would work. Means 
          validation will move to each api's file
        - Not using device API property right now. I am assuming PLUG & BULB are 
          Wyze devices and FAN is a VeSync device
        - Build action class for aliases, maybe validation of action values?
    * FIX ISSUE SETTING COLOR TEMP WHEN COLOR BULB IS OFF
        - I can set color temp of white/non-color bulb whil ebulb is off
        - Doing so with color bulb turns the bulb on
        - Turning the bulb off after setting the color is too slow- not an option
    * Model # is WLPA19C instead of WLPA19
    * Change device type "bulb" to "light" and add "meshlight" to match Wyze device types
    * Min color temp is 1800 instead of 2700
"""

import sys
import os
from os import path
from os import environ
import pickle
import threading
from wyze_sdk import Client
from wyze_sdk.errors import WyzeApiError
from pyvesync import VeSync
from datetime import datetime

SCRIPT_PATH = path.dirname(os.path.realpath(__file__)) + '/'

import home_automation_wyze
import home_automation_vesync


API_WYZE = 'wyze'
API_VESYNC = 'vesync'

DEVICE_NAME = 'device_name'
DEVICE_API = 'device_api'
DEVICE_TYPE = 'device_type'
DEVICE_ID  = 'device_id'

DEVICE_TYPE_PLUG = 'plug'
DEVICE_TYPE_BULB = 'bulb'
DEVICE_TYPE_FAN = 'fan'

ACTION_ON = 'on'
ACTION_OFF = 'off'
ACTION_BRIGHTNESS = 'bright'
ACTION_COLOR_TEMPERATURE = 'temp'
ACTION_FAN_SPEED = 'speed'

ACTION_VALUE_TYPE_BRIGHTNESS = 'brightness'
ACTION_VALUE_TYPE_COLOR_TEMPERATURE = 'color-temperature'
ACTION_VALUE_TYPE_FAN_SPEED = 'fan-speed'


"""
  Variable to store the authenticated clients for all APIs
"""
clients = {
  API_WYZE:     None,
  API_VESYNC:   None
}


"""
  Get client for the requested API

  For speed, always first see if we've already retrieved the client
  for this API. If not, save it here and then return it.

  Inputs:
    * The name of the API to retrieve the client for

  Returns:
    * The authenticated client for the requested API
"""
def get_client(api):
  global clients
  if clients[api] == None:
    if api == 'wyze':
      clients[api] = home_automation_wyze.create_wyze_client(SCRIPT_PATH)
    elif api == 'vesync':
      clients[api] = home_automation_vesync.create_vesync_client(SCRIPT_PATH)

  return clients[api]


"""
  Convert any aliases for action and action_value into the standard
  values.

  Inputs:
    * The action (on|off|bright|temp|warm|cool|fan)
    * The action_value (brightness, color temperature, fan speed)

  Returns:
    * The action
    * The action_value
"""
def convert_aliases(action, action_value):
  action_aliases = {
    'n':           ACTION_ON,
    'f':           ACTION_OFF,

    'brightness':  ACTION_BRIGHTNESS,
    'b':           ACTION_BRIGHTNESS,

    'temperature': ACTION_COLOR_TEMPERATURE,
    't':           ACTION_COLOR_TEMPERATURE,
    'warm':        ACTION_COLOR_TEMPERATURE + '|3000',
    'cool':        ACTION_COLOR_TEMPERATURE + '|6500',

    '1':           ACTION_FAN_SPEED + '|1',
    '2':           ACTION_FAN_SPEED + '|2',
    '3':           ACTION_FAN_SPEED + '|3',
  }
  action = action_aliases.get(action, action)
  if action != None and '|' in action:
    action_and_value = action.split('|')
    action = action_and_value[0]
    action_value = action_and_value[1]
  
  return action, action_value


"""
  Parse the script's parameters into a list of devices (which contains the
  device_name, api, device_type, and device_id), action, and action_value. 
  The device's name is used to find the environment variable that contains
  the device's api, type and id.

  Inputs:
    * Parameters passed into the script
    * Environment variables named HA_DEVICE_xxxx that define
      the api, device type and id for the device

  Returns:
    * The list of devices
       - The device's name
       - The device's API (wyze|vesync)
       - The device's type (plug|bulb)
       - The device's id (Wyze uses MAC address, VeSync uses CID)
    * The action (on|off|bright|temp|warm|cool|fan)
    * The action_value (brightness, color temperature, fan speed)
"""
def parse_parameters(params):
  device_names = params[1].lower() if len(params) > 1 else None
  action = params[2].lower() if len(params) > 2 else None
  action_value = params[3] if len(params) > 3 else None

  action, action_value = convert_aliases(action, action_value)

  if device_names != None:
    devices = []
    for device_name in device_names.split(','):
      device_env_variable = f"HA_DEVICE_{device_name.upper()}"
      device_info = environ.get(device_env_variable)
      if device_info:
        device_parts = device_info.split('|')
        devices.append({
          DEVICE_NAME: device_name, 
          DEVICE_API:  device_parts[0], 
          DEVICE_TYPE: device_parts[1], 
          DEVICE_ID:   device_parts[2]
        })  
      else:
        print(f"Device {device_name} isn't defined- set environment variable {device_env_variable}\n")
        return None, None, None
      
    return devices, action, action_value

  else:
    print(f"device-names is a required field\n")

  return None, None, None


"""
  Validate the action value

  Inputs:
    * Action value type (None|brightness|color-temperature|fan-speed)
    * Action value to validate

  Returns:
    * Is it valid?
"""
def validate_action_value(action_value_type, action_value):
  is_valid = False
  
  if action_value_type == None:
    is_valid = True
  elif action_value_type == ACTION_VALUE_TYPE_BRIGHTNESS:
    is_valid = home_automation_wyze.validate_bulb_action_value('brightness', action_value, home_automation_wyze.WYZE_BULB_BRIGHTNESS_MIN, home_automation_wyze.WYZE_BULB_BRIGHTNESS_MAX)
  elif action_value_type == ACTION_VALUE_TYPE_COLOR_TEMPERATURE:
    is_valid = home_automation_wyze.validate_bulb_action_value('color temperature', action_value, home_automation_wyze.WYZE_BULB_COLOR_TEMPERATURE_MIN, home_automation_wyze.WYZE_BULB_COLOR_TEMPERATURE_MAX)
  elif action_value_type == ACTION_VALUE_TYPE_FAN_SPEED:
    is_valid = home_automation_vesync.validate_fan_action_value('fan speed', action_value, home_automation_vesync.VESYNC_FAN_SPEED_MIN, home_automation_vesync.VESYNC_FAN_SPEED_MAX)
  else:
    print(f"{action_value_type} is an invalid action value type\n")
  
  return is_valid


"""
  Validate the parameters for a single device

  Inputs:
    * The device's name
    * The device's type
    * The action
    * The action's value

  Returns:
    * Is it valid?
"""
def validate_parameters_for_device(device_name, device_type, action, action_value):
  validations = {
    DEVICE_TYPE_PLUG: { ACTION_ON:                     None,
                        ACTION_OFF:                    None }, 
    DEVICE_TYPE_BULB: { ACTION_ON:                     None,
                        ACTION_OFF:                    None,
                        ACTION_BRIGHTNESS:             ACTION_VALUE_TYPE_BRIGHTNESS,
                        ACTION_COLOR_TEMPERATURE:      ACTION_VALUE_TYPE_COLOR_TEMPERATURE },
    DEVICE_TYPE_FAN:  { ACTION_ON:                     None,
                        ACTION_OFF:                    None,
                        ACTION_FAN_SPEED:              ACTION_VALUE_TYPE_FAN_SPEED }
  }

  is_valid = False
  if device_type in validations:
    if action in validations[device_type]:
      action_value_type = validations[device_type][action]
      is_valid = validate_action_value(action_value_type, action_value)
    else:
      if action == None:
        print("action is a required field\n")
      else:
        print(f"{action} is not a valid action for {device_name}\n")
  else:
    print(f"{device_type} is not a valid device type\n")

  return is_valid


"""
  Validate the parameters for all the devices, to ensure that we don't try to
  set the brightness on a smart plug.

  Inputs:
    * The list of devices (with name, api, type, and id)
    * The action
    * The action's value

  Returns:
    * Is it valid?
"""
def validate_parameters(devices, action, action_value):
  is_valid = False
  if devices != None:
    for device in devices:
      is_valid = validate_parameters_for_device(device[DEVICE_NAME], device[DEVICE_TYPE], action, action_value)
      if not is_valid: break

  return is_valid


"""
  Display the help
"""
def display_help():
  # TODO- Add fan speed
  print('Syntax:')
  print(f"  home_automation.py <device-names> <action> <action-value>")
  print(f"    <device-names>:   comma-separated-list of one or more devices (i.e. fan|ac|litetop|etc)")
  print(f"")
  print(f"    For plugs:")
  print(f"      <action>:       {ACTION_ON}|{ACTION_OFF}")
  print(f"")
  print(f"    For bulbs:")
  print(f"      <action>:       {ACTION_ON}|{ACTION_OFF}|{ACTION_BRIGHTNESS}|{ACTION_COLOR_TEMPERATURE}")
  print(f"      <action-type>:  action '{ACTION_BRIGHTNESS}' requires either")
  print(f"                        a number between {home_automation_wyze.WYZE_BULB_BRIGHTNESS_MIN} and {home_automation_wyze.WYZE_BULB_BRIGHTNESS_MAX}")
  print(f"                        or +|- to increase/decrease brightness by 10%")
  print(f"                      action '{ACTION_BRIGHTNESS}' requires either")
  print(f"                        a number between {home_automation_wyze.WYZE_BULB_COLOR_TEMPERATURE_MIN} and {home_automation_wyze.WYZE_BULB_COLOR_TEMPERATURE_MAX}")
  print(f"                        or +|- to increase/decrease color temperature by 10%")
  print(f"")
  print(f"    For fans/air purifiers:")
  print(f"      <action>:       {ACTION_ON}|{ACTION_OFF}|{ACTION_FAN_SPEED}")
  print(f"      <action-type>:  action '{ACTION_FAN_SPEED}' requires a number 1-3")
  print(f"                        Setting the fan speed does NOT turn the fan/air purifier on")
  print(f"")
  print(f"Examples:")
  print(f"  home_automation.py fan on")
  print(f"  home_automation.py fan,ac off")
  print(f"  home_automation.py litetop on")
  print(f"  home_automation.py litetop bright 25")
  print(f"  home_automation.py litetop bright +")
  print(f"  home_automation.py litetop temp 3800")
  print(f"  home_automation.py litetop,litebottom off")
  print(f"  home_automation.py ac fan 3")
  print(f"")
  print(f"Aliases for various actions:")
  print(f"  n              =>  {ACTION_ON}")
  print(f"  f              =>  {ACTION_OFF}")
  print(f"  b/brightness   =>  {ACTION_BRIGHTNESS}")
  print(f"  t/temperature  =>  {ACTION_COLOR_TEMPERATURE}")
  print(f"  warm           =>  {ACTION_COLOR_TEMPERATURE} 3000")
  print(f"  cool           =>  {ACTION_COLOR_TEMPERATURE} 6500")
  print(f"  1              =>  {ACTION_FAN_SPEED} 1")
  print(f"  2              =>  {ACTION_FAN_SPEED} 2")
  print(f"  3              =>  {ACTION_FAN_SPEED} 3")



def main(params):
  devices, action, action_value = parse_parameters(params)

  if not validate_parameters(devices, action, action_value):
    display_help()
  else:
    actions = {
      DEVICE_TYPE_PLUG: home_automation_wyze.plug_action,
      DEVICE_TYPE_BULB: home_automation_wyze.bulb_action,
      DEVICE_TYPE_FAN:  home_automation_vesync.fan_action
    }

    # Run each device's command in a thread so they run in parallel
    thread_list = []
    for device in devices:
      thread = threading.Thread(
        target=actions[device[DEVICE_TYPE]], 
        args=(get_client(device[DEVICE_API]), device[DEVICE_ID], action, action_value))
      thread_list.append(thread)
      thread.start()
    
    # Wait for all the threads to finish
    for thread in thread_list:
      thread.join()  




"""
  Only run this if running from a script
"""
if __name__ == '__main__':
  main(sys.argv)
  #home_automation_wyze.dump_wyze_devices(SCRIPT_PATH)
  #home_automation_vesync.dump_vesync_devices(SCRIPT_PATH)
