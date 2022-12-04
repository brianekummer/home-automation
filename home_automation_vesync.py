"""
  Home automation script
  by Brian Kummer, Sept 2021
  
  This class supports devices using the following unofficial VeSync API
    - https://github.com/webdjoe/pyvesync
"""
import os
from os import path
from os import environ
import pickle
import time
from datetime import datetime
from pyvesync import VeSync

VESYNC_CLIENT_FILENAME = 'vesync_client.pickle'

ACTION_GET = 'get'
ACTION_ON = 'on'
ACTION_OFF = 'off'
ACTION_TOGGLE = 'toggle'
ACTION_FAN_SPEED = 'speed'

VESYNC_FAN_SPEED_MIN = 1
VESYNC_FAN_SPEED_MAX = 3

MY_TIMEZONE = datetime.now().astimezone().tzinfo


"""
  Log into VeSync, caching the authenticated client to a file.

  Returns:
    * The authenticated client
"""
def create_vesync_client(script_path):
  # TODO- Remove logging of time it takes to create this client
  new_client = None
  client_pathname = os.path.join(script_path, VESYNC_CLIENT_FILENAME)
  log_file = open(os.path.join(script_path, 'vesync_login.log'), 'a')
  log_text = ''
  start_time = time.time()
  if path.exists(client_pathname):
    #try:
    log_text = 'READ'
    new_client = pickle.load(open(client_pathname, 'rb'))

    # The list of devices is contained in new_client. Calling new_client.update()
    # every time we login guarantees that we have the latest list of devices,
    # but slows things down.
    # new_client.update()
      
    # TODO- Questions:
    #   - Does login expire?
    #   - What happens if I change the password- what kind of error do I get,
    #     and can I catch that?
    #except WyzeApiError as e:
    #  if 'The access token has expired' in e.args[0]:
    #    new_client = None
    #    log_text += ', EXPIRED, '

  if new_client == None:
    log_text += 'CREATED'
    new_client = VeSync(environ.get('HA_EMAIL'), environ.get('HA_VESYNC_PASSWORD'), MY_TIMEZONE)
    new_client.login()
    new_client.update()
    pickle.dump(new_client, open(client_pathname, 'wb'))

  end_time = time.time()
  log_text = datetime.now().strftime("%m/%d/%Y %H:%M:%S") + f"- {round(end_time-start_time, 3)} sec- " + log_text + "\n"
  log_file.write(log_text)
  log_file.close()

  return new_client


"""
  Validate the requested fan speed

  Inputs:
    * property_name is the name of the property
    * property_value is the requested value of the property

  Returns:
    * Is it valid?
"""
def validate_fan_action_value(property_name, property_value, min_value, max_value):
  is_valid = False

  if property_value == None:
    print(f"action-value is a required field\n")
  elif property_value.isnumeric() and min_value <= int(property_value) <= max_value:
    is_valid = True
  elif property_value == "cycle":
    is_valid = True
  else:
    print(f"{property_value} is not a valid {property_name} value\n")
  
  return is_valid


"""
  Fan actions
"""
def fan_action_get(client, fan, action_value):
  fan.get_details()
  # TODO- I have no idea if this works, or if I need to replicate dump_device() 
  # from home_automation_wyze.py.
  print(fan)
def fan_action_on(client, fan, action_value):
  fan.turn_on()
def fan_action_off(client, fan, action_value):
  fan.turn_off()
def fan_action_toggle(client, fan, action_value):
  fan.get_details()
  fan.toggle_switch(fan.device_status == 'off')
def fan_action_speed(client, fan, action_value):
  # FYI, changing the fan speed does NOT turn the fan on
  if action_value == "cycle":
    fan.get_details()
    fan_speed = fan.fan_level
    fan_speed = 1 if fan_speed == 3 else fan_speed+1
    fan.change_fan_speed(fan_speed)
  else:
    fan.change_fan_speed(int(action_value))



"""
  Perform an action on a fan

  Inputs:
    * The device's id
    * The action to perform on the device
    * The value for the action (speed)

  Outputs:
    * Turns the fan on or off
      OR
    * Sets the fan's speed
"""
def fan_action(client, device_id, action, action_value):
  fan = next((f for f in client.fans if f.cid == device_id), None)
  fan_actions = {
    ACTION_GET:        fan_action_get,
    ACTION_OFF:        fan_action_off,
    ACTION_ON:         fan_action_on,
    ACTION_TOGGLE:     fan_action_toggle,
    ACTION_FAN_SPEED:  fan_action_speed
  }
  fan_actions[action](client, fan, action_value)


"""
  Debugging tool
"""
def dump_vesync_devices(script_path):
  client = create_vesync_client(script_path)

  for device in client.fans:
    device.get_details()
    device.display()
