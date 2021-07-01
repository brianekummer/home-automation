"""
  Home automation script for Wyze devices
  by Brian Kummer, June 2021
  
  Uses this unofficial API: https://pypi.org/project/wyze-sdk/,
  which requires Python 3.8 or higher.

  Syntax:
    wyze.py <device-names> <action> <action-value>
      (see main body for details and examples)

  Assumptions:
    * This script expects the following environment variables to be set
        - For authentication, which requires 2FA on my Wyze account to be
          disabled
            WYZE_EMAIL="xxxxx@gmail.com"
            WYZE_PASSWORD="xxxxxxxx"
        - Each device needs to have an environment variable (set in 
          ~/.env) with its type and MAC address, like these:
            WYZE_DEVICE_FAN="plug|ABABABABABAB"
            WYZE_DEVICE_LITE="bulb|121212121212"
    * Wyz

  Notes:
    * Authenticating every time I call this script is unnecessarily slow,
      so I cache the authenticated client and read it from disk instead of
      regenerating it every time I run this script.
"""


import sys
import os
import pickle
import threading
from wyze_sdk import Client
from wyze_sdk.errors import WyzeApiError
from os import path
from os import environ


# TODO- REMOVE THESE
import time
from datetime import datetime


SCRIPT_PATH = os.path.dirname(os.path.realpath(__file__)) + '/'

# Ensure cached credentials are in same folder as this script
WYZE_CLIENT_FILENAME = SCRIPT_PATH + 'wyze_client.txt'

DEVICE_NAME = 'device_name'
DEVICE_TYPE = 'device_type'
DEVICE_MAC  = 'device_mac'

DEVICE_TYPE_PLUG = 'plug'
DEVICE_TYPE_BULB = 'bulb'

ACTION_ON = 'on'
ACTION_OFF = 'off'
ACTION_BRIGHTNESS = 'bright'
ACTION_COLOR_TEMPERATURE = 'temp'

ACTION_VALUE_TYPE_BRIGHTNESS = 'brightness'
ACTION_VALUE_TYPE_COLOR_TEMPERATURE = 'color-temperature'

WYZE_BULB_BRIGHTNESS_MIN = 1
WYZE_BULB_BRIGHTNESS_MAX = 100
WYZE_BULB_BRIGHTNESS_INTERVAL = (WYZE_BULB_BRIGHTNESS_MAX - WYZE_BULB_BRIGHTNESS_MIN)/5
WYZE_BULB_COLOR_TEMPERATURE_MIN = 2700
WYZE_BULB_COLOR_TEMPERATURE_MAX = 6500
WYZE_BULB_COLOR_TEMPERATURE_INTERVAL = (WYZE_BULB_COLOR_TEMPERATURE_MAX - WYZE_BULB_COLOR_TEMPERATURE_MIN)/5


"""
  Create the Wyze authenticated client, caching it to a file.

  Returns:
    * The authenticated client
"""
def create_wyze_client():
  client = None
  # TODO- Remove logging of time it takes to create this client
  log_file = open(SCRIPT_PATH + "wyze_login.log", "a")
  log_text = ""
  start_time = time.time()
  if path.exists(WYZE_CLIENT_FILENAME):
    try:
      log_text = 'READ'
      client = pickle.load(open(WYZE_CLIENT_FILENAME, 'rb'))
      client.api_test()
    except WyzeApiError as e:
      if 'The access token has expired' in e.args[0]:
        client = None
        log_text += ', EXPIRED, '

  if client == None:
    log_text += 'CREATED'
    client = Client(email=environ.get('WYZE_EMAIL'), password=environ.get('WYZE_PASSWORD'))
    pickle.dump(client, open(WYZE_CLIENT_FILENAME, 'wb'))

  end_time = time.time()
  log_text = datetime.now().strftime("%m/%d/%Y %H:%M:%S") + f"- {round(end_time-start_time, 3)} sec- " + log_text + "\n"
  log_file.write(log_text)
  log_file.close()

  return client


"""
  Convert any aliases for action and action_value into the standard
  values.

  Inputs:
    * The action (on|off|bright|temp|warm|cool)
    * The action_value (brightness, color temperature)

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
    'cool':        ACTION_COLOR_TEMPERATURE + '|6500'
  }
  action = action_aliases.get(action, action)
  if action != None and "|" in action:
    action_and_value = action.split("|")
    action = action_and_value[0]
    action_value = action_and_value[1]
  
  return action, action_value


"""
  Parse the script's parameters into a list of devices (which contains the
  device_name, device_type, and device_mac), action, and action_value. 
  The device's name is used to find the environment variable that contains
  the device's type and MAC address.

  Inputs:
    * Parameters passed into the script
    * Environment variables named WYZE_DEVICE_xxxx that define
      the device type and MAC address for the device

  Returns:
    * The list of devices
       - The device's name
       - The device's type (plug|bulb)
       - The device's MAC address
    * The action (on|off|bright|temp|warm|cool)
    * The action_value (brightness, color temperature)
"""
def parse_parameters(params):
  device_names = params[1].lower() if len(params) > 1 else None
  action = params[2].lower() if len(params) > 2 else None
  action_value = params[3] if len(params) > 3 else None

  action, action_value = convert_aliases(action, action_value)

  if device_names != None:
    devices = []
    for device_name in device_names.split(','):
      device_env_variable = f"WYZE_DEVICE_{device_name.upper()}"
      device_info = environ.get(device_env_variable)
      if device_info:
        device_parts = device_info.split('|')
        devices.append({
          DEVICE_NAME: device_name, 
          DEVICE_TYPE: device_parts[0], 
          DEVICE_MAC:  device_parts[1]
        })  
      else:
        print(f"Device {device_name} isn't defined- set environment variable {device_env_variable}\n")
        return None, None, None
      
    return devices, action, action_value

  else:
    print(f"device-names is a required field\n")

  return None, None, None


"""
  Validate the requested bulb property
    * Must be either 
        - numeric and between a min and max value
        - +/- to increase/decrease by a percentage

  Inputs:
    * property_name is the name of the property
    * property_value is the requested value of the property

  Returns:
    * Is it valid?
"""
def validate_bulb_action_value(property_name, property_value, min_value, max_value):
  is_valid = False

  if property_value == None:
    print(f"action-value is a required field\n")
  elif property_value in {'+', '-'}:
     is_valid = True
  elif property_value.isnumeric() and min_value <= int(property_value) <= max_value:
    is_valid = True
  else:
    print(f"{property_value} is not a valid {property_name} value\n")
  
  return is_valid


"""
  Validate the action value

  Inputs:
    * Action value type (None|brightness|color-temperature)
    * Action value to validate

  Returns:
    * Is it valid?
"""
def validate_action_value(action_value_type, action_value):
  is_valid = False
  
  if action_value_type == None:
    is_valid = True
  elif action_value_type == ACTION_VALUE_TYPE_BRIGHTNESS:
    is_valid = validate_bulb_action_value('brightness', action_value, WYZE_BULB_BRIGHTNESS_MIN, WYZE_BULB_BRIGHTNESS_MAX)
  elif action_value_type == ACTION_VALUE_TYPE_COLOR_TEMPERATURE:
    is_valid = validate_bulb_action_value('color temperature', action_value, WYZE_BULB_COLOR_TEMPERATURE_MIN, WYZE_BULB_COLOR_TEMPERATURE_MAX)
  else:
    print(f"{action_value_type} is an invalid action value type\n")
  
  return is_valid


"""
  Validate the parameters for a single device

  Inputs:
    * The device's name
    # The device's type
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
                        ACTION_COLOR_TEMPERATURE:      ACTION_VALUE_TYPE_COLOR_TEMPERATURE }
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
        print(f"{action} is not a valid action for {device_name}\n")
  else:
    print(f"{device_type} is not a valid device type\n")

  return is_valid


"""
  Validate the parameters for all the devices, to ensure that we don't try to
  set the brightness on a smart plug.

  Inputs:
    * The list of devices (with name, type, and MAC)
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
  Plug actions
"""
def plug_action_off(plug):
  client.plugs.turn_off(device_mac=plug.mac, device_model=plug.product.model)
def plug_action_on(plug):
  client.plugs.turn_on(device_mac=plug.mac, device_model=plug.product.model)


"""
  Perform an action on a plug

  Inputs:
    * The device's MAC address
    * The action to perform on the device
    * The action value- is None and unused for plugs

  Outputs:
    * Turns the plug on or off
"""
def plug_action(device_mac, action, action_value):
  plug = client.plugs.info(device_mac=device_mac)
  plug_actions = {
    ACTION_OFF:  plug_action_off,
    ACTION_ON:   plug_action_on
  }
  plug_actions[action](plug)


"""
  Bulb actions
"""
def bulb_action_on(bulb, action_value):
  client.bulbs.turn_on(device_mac=bulb.mac, device_model=bulb.product.model)
def bulb_action_off(bulb, action_value):
  client.bulbs.turn_off(device_mac=bulb.mac, device_model=bulb.product.model)
def bulb_action_brightness(bulb, action_value):
  brightness = {
    '+': min(bulb.brightness + WYZE_BULB_BRIGHTNESS_INTERVAL, WYZE_BULB_BRIGHTNESS_MAX),
    '-': max(bulb.brightness - WYZE_BULB_BRIGHTNESS_INTERVAL, WYZE_BULB_BRIGHTNESS_MIN)
  }
  new_brightness = int(brightness.get(action_value, action_value))
  client.bulbs.set_brightness(device_mac=bulb.mac, device_model=bulb.product.model, brightness=new_brightness)
def bulb_action_color_temperature(bulb, action_value):
  color_temperature = {
    '+': min(bulb.color_temp + WYZE_BULB_COLOR_TEMPERATURE_INTERVAL, WYZE_BULB_COLOR_TEMPERATURE_MAX),
    '-': max(bulb.color_temp - WYZE_BULB_COLOR_TEMPERATURE_INTERVAL, WYZE_BULB_COLOR_TEMPERATURE_MIN),
  }
  new_color_temperature = int(color_temperature.get(action_value, action_value))
  client.bulbs.set_color_temp(device_mac=bulb.mac, device_model=bulb.product.model, color_temp=new_color_temperature)


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
  bulb_actions = {
    ACTION_OFF:                    bulb_action_off,
    ACTION_ON:                     bulb_action_on,
    ACTION_BRIGHTNESS:             bulb_action_brightness,
    ACTION_COLOR_TEMPERATURE:      bulb_action_color_temperature
  }
  bulb_actions[action](bulb, action_value)


"""
  Display the help
"""
def display_help():
  print('Syntax:')
  print(f"  wyze.py <device-names> <action> <action-value>")
  print(f"    <device-names>:   comma-separated-list of one or more devices (i.e. fan|ac|lite|etc)")
  print(f"")
  print(f"    For plugs:")
  print(f"      <action>:       {ACTION_ON}|{ACTION_OFF}")
  print(f"")
  print(f"    For bulbs:")
  print(f"      <action>:       {ACTION_ON}|{ACTION_OFF}|{ACTION_BRIGHTNESS}|{ACTION_COLOR_TEMPERATURE}")
  print(f"      <action-type>:  action '{ACTION_BRIGHTNESS}' requires either")
  print(f"                        a number between {WYZE_BULB_BRIGHTNESS_MIN} and {WYZE_BULB_BRIGHTNESS_MAX}")
  print(f"                        or +|- to increase/decrease brightness by 10%")
  print(f"                      action '{ACTION_BRIGHTNESS}' requires either")
  print(f"                        a number between {WYZE_BULB_COLOR_TEMPERATURE_MIN} and {WYZE_BULB_COLOR_TEMPERATURE_MAX}")
  print(f"                        or +|- to increase/decrease color temperature by 10%")
  print(f"")
  print(f"Examples:")
  print(f"  wyze.py fan on")
  print(f"  wyze.py fan,ac off")
  print(f"  wyze.py litetop on")
  print(f"  wyze.py litetop bright 25")
  print(f"  wyze.py litetop bright +")
  print(f"  wyze.py litetop temp 3800")
  print(f"  wyze.py litetop,litebottom off")
  print(f"")
  print(f"Aliases for various actions:")
  print(f"  n              =>  {ACTION_ON}")
  print(f"  f              =>  {ACTION_OFF}")
  print(f"  b/brightness   =>  {ACTION_BRIGHTNESS}")
  print(f"  t/temperature  =>  {ACTION_COLOR_TEMPERATURE}")
  print(f"  warm           =>  {ACTION_COLOR_TEMPERATURE} 3000")
  print(f"  cool           =>  {ACTION_COLOR_TEMPERATURE} 6500")


"""
  Main body 
"""
is_valid = False
devices, action, action_value = parse_parameters(sys.argv)

if not validate_parameters(devices, action, action_value):
  display_help()
else:
  client = create_wyze_client()

  actions = {
    DEVICE_TYPE_PLUG: plug_action,
    DEVICE_TYPE_BULB: bulb_action
  }

  # Run each device's command in a thread so they run in parallel
  thread_list = []
  for device in devices:
    thread = threading.Thread(target=actions[device[DEVICE_TYPE]], args=(device[DEVICE_MAC], action, action_value))
    thread_list.append(thread)
    thread.start()
  
  # Wait for all the threads to finish
  for thread in thread_list:
    thread.join()