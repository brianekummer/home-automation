"""
  Home automation script
  by Brian Kummer, Sept 2021
  
  This class supports Wyze devices using the following unofficial API
    - https://pypi.org/project/wyze-sdk/ requires Python 3.8 or higher
"""
import sys
import os
from os import path
from os import environ
import pickle
import time
from datetime import datetime
from wyze_sdk import Client
from wyze_sdk.errors import WyzeApiError

WYZE_CLIENT_FILENAME = 'wyze_client.pickle'

ACTION_ON = 'on'
ACTION_OFF = 'off'
ACTION_BRIGHTNESS = 'bright'
ACTION_COLOR_TEMPERATURE = 'temp'

WYZE_BULB_BRIGHTNESS_MIN = 1
WYZE_BULB_BRIGHTNESS_MAX = 100
WYZE_BULB_BRIGHTNESS_INTERVAL = (WYZE_BULB_BRIGHTNESS_MAX - WYZE_BULB_BRIGHTNESS_MIN)/5
WYZE_BULB_COLOR_TEMPERATURE_MIN = 2700
WYZE_BULB_COLOR_TEMPERATURE_MAX = 6500
WYZE_BULB_COLOR_TEMPERATURE_RANGE = WYZE_BULB_COLOR_TEMPERATURE_MAX - WYZE_BULB_COLOR_TEMPERATURE_MIN
WYZE_BULB_COLOR_TEMPERATURE_INTERVAL = (WYZE_BULB_COLOR_TEMPERATURE_RANGE)/5


"""
  Create the Wyze authenticated client, caching it to a file.

  Returns:
    * The authenticated client
"""
def create_wyze_client(script_path):
  # TODO- Remove logging of time it takes to create this client
  new_client = None
  client_pathname = os.path.join(script_path, WYZE_CLIENT_FILENAME)
  log_file = open(script_path + 'wyze_login.log', 'a')
  log_text = ''
  start_time = time.time()
  if path.exists(client_pathname):
    try:
      log_text = 'READ'
      new_client = pickle.load(open(client_pathname, 'rb'))

      # api_test() does not require valid credentials, so use
      # devices_list() to ensure our credentials are valid
      response = new_client.devices_list()
      
    except WyzeApiError as e:
      if 'The access token has expired' in e.args[0]:
        new_client = None
        log_text += ', EXPIRED, '

  if new_client == None:
    log_text += 'CREATED'
    new_client = Client(email=environ.get('HA_EMAIL'), password=environ.get('HA_WYZE_PASSWORD'))
    pickle.dump(new_client, open(client_pathname, 'wb'))

  end_time = time.time()
  log_text = datetime.now().strftime("%m/%d/%Y %H:%M:%S") + f"- {round(end_time-start_time, 3)} sec- " + log_text + "\n"
  log_file.write(log_text)
  log_file.close()

  return new_client


"""
  Plug actions
"""
def plug_action_off(client, plug):
  client.plugs.turn_off(device_mac=plug.mac, device_model=plug.product.model)
def plug_action_on(client, plug):
  client.plugs.turn_on(device_mac=plug.mac, device_model=plug.product.model)


"""
  Perform an action on a plug

  Inputs:
    * The device's id (MAC address)
    * The action to perform on the device
    * The action value- is None and unused for plugs

  Outputs:
    * Turns the plug on or off
"""
def plug_action(client, device_id, action, action_value):
  plug = client.plugs.info(device_mac=device_id)
  plug_actions = {
    ACTION_OFF:  plug_action_off,
    ACTION_ON:   plug_action_on
  }
  plug_actions[action](client, plug)


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
  Bulb actions
"""
def bulb_action_on(client, bulb, action_value):
  client.bulbs.turn_on(device_mac=bulb.mac, device_model=bulb.product.model)
def bulb_action_off(client, bulb, action_value):
  client.bulbs.turn_off(device_mac=bulb.mac, device_model=bulb.product.model)
def bulb_action_brightness(client, bulb, action_value):
  brightness = {
    '+': min(bulb.brightness + WYZE_BULB_BRIGHTNESS_INTERVAL, WYZE_BULB_BRIGHTNESS_MAX),
    '-': max(bulb.brightness - WYZE_BULB_BRIGHTNESS_INTERVAL, WYZE_BULB_BRIGHTNESS_MIN)
  }
  new_brightness = int(brightness.get(action_value, action_value))
  client.bulbs.set_brightness(device_mac=bulb.mac, device_model=bulb.product.model, brightness=new_brightness)
def bulb_action_color_temperature(client, bulb, action_value):
  color_temperature = {
    '+': min(bulb.color_temp + WYZE_BULB_COLOR_TEMPERATURE_INTERVAL, WYZE_BULB_COLOR_TEMPERATURE_MAX),
    '-': max(bulb.color_temp - WYZE_BULB_COLOR_TEMPERATURE_INTERVAL, WYZE_BULB_COLOR_TEMPERATURE_MIN),
  }
  new_color_temperature = int(color_temperature.get(action_value, action_value))

  # While we can set the temperature of a (non-color) Light while it is off, doing
  # the same to a (color) MeshLight turns it on, which I don't want. So we will 
  # only set the temperature of a MeshLight if it is currently on.
  if bulb.type == 'Light' or (bulb.type == 'MeshLight' and bulb.is_on):
    client.bulbs.set_color_temp(device_mac=bulb.mac, device_model=bulb.product.model, color_temp=new_color_temperature)


"""
  Perform an action on a light bulb

  Inputs:
    * The device's id (MAC address)
    * The action to perform on the device
    * The value for the action (brightness or color temperature)

  Outputs:
    * Turns the bulb on or off
      OR
    * Sets the bulb's brightness
      OR
    * Sets the bulb's color temperature
"""
def bulb_action(client, device_id, action, action_value):
  bulb = client.bulbs.info(device_mac=device_id)
  bulb_actions = {
    ACTION_OFF:                    bulb_action_off,
    ACTION_ON:                     bulb_action_on,
    ACTION_BRIGHTNESS:             bulb_action_brightness,
    ACTION_COLOR_TEMPERATURE:      bulb_action_color_temperature
  }
  bulb_actions[action](client, bulb, action_value)


"""
  Debugging tool
"""
def dump_wyze_devices():
  client = create_wyze_client()

  for device in client.devices_list():
    print(f"mac: {device.mac}")
    print(f"nickname: {device.nickname}")
    print(f"is_online: {device.is_online}")
    print(f"product model: {device.product.model}")
    print(f"type: {device.type}")
    if device.type == "Light" or device.type == "MeshLight":
      bulb = client.bulbs.info(device_mac=device.mac)
      print(f"type: {bulb.type}")
      print(f"away_mode: {bulb.away_mode}")
      print(f"power_loss_recovery: {bulb.power_loss_recovery}")
      print(f"switch_state: {bulb.switch_state}")
      print(f"power: {bulb.is_on}")
      print(f"brightness: {bulb.brightness}")
      print(f"temp: {bulb.color_temp}")
      if device.type == "MeshLight":
        print(f"color: {bulb.color}")
    print(f"")
