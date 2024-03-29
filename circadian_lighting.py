"""
  Circadian Lighting

  Syntax:
    circadian_lighting.py <latitude> <longitude> <device-names> [<current_time_as_local>]

    python3 circadian_lighting.py 40.33, -80.33 litetop,litebottom
    python3 circadian_lighting.py 40.33, -80.33 litetop,litebottom 2021-07-04T14:00:00.000-04:00
  
  How will crontab use it? w/o time. time is only useful for testing, so assume that is local time

  I'm experimenting with using civil_twilight_end instead of sunset, is about a half hour later

  TO DO- Add validation/help
  

"""

import os
from os import path
import pickle
import sys
import requests
from datetime import date
from datetime import datetime

import home_automation
import home_automation_wyze

SCRIPT_PATH = path.dirname(path.realpath(__file__)) + '/'
SUNRISE_SUNSET_CACHE_FILENAME = SCRIPT_PATH + 'sunrise_sunset.pickle'

MY_TIMEZONE = datetime.now().astimezone().tzinfo
#print(MY_TIMEZONE)


def get_sunrise(results): 
  return datetime.fromisoformat(results['sunrise']).astimezone(MY_TIMEZONE)

def get_solar_noon(results):
  return datetime.fromisoformat(results['solar_noon']).astimezone(MY_TIMEZONE)

def get_sunset(results):
  #return datetime.fromisoformat(results['sunset']).astimezone(MY_TIMEZONE)
  return datetime.fromisoformat(results['civil_twilight_end']).astimezone(MY_TIMEZONE)
    


def get_sunrise_sunset(latitude, longitude, todays_date):
  results = None
  if path.exists(SUNRISE_SUNSET_CACHE_FILENAME):
    results = pickle.load(open(SUNRISE_SUNSET_CACHE_FILENAME, 'rb'))

  today_at_midnight = datetime.combine(date.today(), datetime.min.time()).astimezone(MY_TIMEZONE)

  if results == None or get_sunrise(results) < today_at_midnight:
    print("Retrieving sunrise and sunset from internet")
    response = requests.get(f"https://api.sunrise-sunset.org/json?lat={latitude}&lng={longitude}&formatted=0&date={todays_date}")
    #print(response.json())
    results = response.json()['results']
    pickle.dump(results, open(SUNRISE_SUNSET_CACHE_FILENAME, 'wb'))
  
  return results


def get_solar_times_as_local_time(latitude, longitude, todays_date):
  results = get_sunrise_sunset(latitude, longitude, todays_date)
  #print(f"UTC: {results['sunrise']}, {results['solar_noon']}, {results['civil_twilight_end']}")

  # Convert times from UTC to local time
  sunrise = get_sunrise(results)
  solar_noon = get_solar_noon(results)
  sunset = get_sunset(results)
  #print(f"LOCAL: {sunrise}, {solar_noon}, {sunset}")

  return sunrise, solar_noon, sunset


params = sys.argv
latitude = params[1].lower() if len(params) > 1 else None
longitude = params[2].lower() if len(params) > 2 else None
device_names = params[3].lower() if len(params) > 3 else None
now = datetime.fromisoformat(params[4]) if len(params) > 4 else datetime.now().astimezone(MY_TIMEZONE)
#print(f"params={params}, device_name={device_names}, now={now}")

sunrise, solar_noon, sunset = get_solar_times_as_local_time(latitude, longitude, now.strftime('%Y-%m-%d'))

new_temperature = None
TEMP_MORNING_START_COLOR_TEMPERATURE = 4000
if now < sunrise:
  #new_temperature = home_automation_wyze.WYZE_BULB_COLOR_TEMPERATURE_MIN
  new_temperature = TEMP_MORNING_START_COLOR_TEMPERATURE
  print(f"Before sunrise. Temp={new_temperature}")

elif sunrise < now < solar_noon:
  duration_in_sec = (solar_noon - sunrise).total_seconds()
  sec_since_start = (now - sunrise).total_seconds()
  percentage_thru_duration = sec_since_start/duration_in_sec

  # Seeing how this works- start the day with a much cooler temp
  #new_temperature = home_automation_wyze.WYZE_BULB_COLOR_TEMPERATURE_MIN + round(home_automation_wyze.WYZE_BULB_COLOR_TEMPERATURE_RANGE * percentage_thru_duration)
  new_temperature = TEMP_MORNING_START_COLOR_TEMPERATURE + round((home_automation_wyze.WYZE_BULB_COLOR_TEMPERATURE_MAX - TEMP_MORNING_START_COLOR_TEMPERATURE) * percentage_thru_duration)
  
  print(f"Morning. duration_in_sec={duration_in_sec}, sec_since_start={sec_since_start}, percentage_thru_duration = {percentage_thru_duration}, new_temperature = {new_temperature}")

elif solar_noon < now < sunset:
  duration_in_sec = (sunset - solar_noon).total_seconds()
  sec_since_start = (now - solar_noon).total_seconds()
  percentage_thru_duration = sec_since_start/duration_in_sec
  new_temperature = home_automation_wyze.WYZE_BULB_COLOR_TEMPERATURE_MAX - round(home_automation_wyze.WYZE_BULB_COLOR_TEMPERATURE_RANGE * percentage_thru_duration)
  print(f"Afternoon/evening. duration_in_sec={duration_in_sec}, sec_since_start={sec_since_start}, percentage_thru_duration = {percentage_thru_duration}, new_temperature = {new_temperature}")

elif now > sunset:
  new_temperature = home_automation_wyze.WYZE_BULB_COLOR_TEMPERATURE_MIN
  print(f"After sunset. Temp={new_temperature}")

# Call my wyze program to set the temperature
home_automation.main(['home_automation.py', device_names, 'temperature', str(new_temperature)])
