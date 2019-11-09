# location plugins
# Copyright (C) 2019  Anthony DeDominic <adedomin@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
# currently supporting: time, weather
# author: afloat
#
# usage:
#  .w [LOCATION]                 -- check the weather in a specific
#                                   location



# import core db functions
from core import db, hook

import json
import urllib

location_column = 'location'

# capped at 5 for now
# see day_qualifiers
forecast_days = 2


def _get_apixu_api_key(client):
    """This function tries to get the APIXU appID from config"""
    try:
        APIXU_KEY = client.bot.config['api_keys']['APIXU']
        return APIXU_KEY
    except KeyError:
        return ''


def _update_user_location(conn, location_column, location_value, username):
    db.set_cell(conn, 'users', location_column, location_value, 'nick', username)
    db.ccache()
    return


def _get_user_location(conn, location_column, username):
    location = db.get_cell(conn, 'users', location_column, 'nick', username)
    try:
        if location[0][0] is None or len(location[0][0]) == 0:
                return None
    except:
        return None

    return location[0][0]


def _build_time_response(j_weather):
    return "[" + j_weather["location"]["tz_id"] + "] " + str(j_weather["location"]["localtime"]) + " in " + j_weather["location"]["name"]


def _build_weather_response(j_weather):
    high = "High: "
    low = "Low: "

    location = "\02" + j_weather["location"]["name"] + ", " + j_weather["location"]["region"] + ", " + j_weather["location"]["country"] + "\02"
    cur_qualifier = "\02" + " - Current: " + "\02"
    cur_cond = j_weather["current"]["condition"]["text"] + ", " + str(int(j_weather["current"]["temp_c"])) + "C/" + str(int(j_weather["current"]["temp_f"])) + "F, "
    cur_humidity = "Humidity: " + str(j_weather["current"]["humidity"]) + "%, "
    cur_wind = "Wind: " + str(int(j_weather["current"]["wind_kph"])) + "KPH/" + str(int(j_weather["current"]["wind_mph"])) + "MPH, "
    cur_uv = "UV: " + str(int(j_weather["current"]["uv"])) + ". "
    current = location + cur_qualifier + cur_cond + cur_humidity + cur_wind + cur_uv

    def _build_forecast_response(days):
        forecast_responses = []
        day_qualifiers = ["Today", "Tomorrow", "Two Days Away", "Three Days Away", "Four Days Away"]
        for i in range(days):
            cond = j_weather["forecast"]["forecastday"][i]["day"]["condition"]["text"] + ", " + high + str(int(j_weather["forecast"]["forecastday"][i]["day"]["maxtemp_c"])) + "C/" + str(int(j_weather["forecast"]["forecastday"][i]["day"]["maxtemp_f"])) + "F, " + low + str(int(j_weather["forecast"]["forecastday"][i]["day"]["mintemp_c"])) + "C/" + str(int(j_weather["forecast"]["forecastday"][i]["day"]["mintemp_f"])) + "F."
            forecast_responses.append("\02" + day_qualifiers[i] + "\02" + ": " + cond)
        return forecast_responses

    forecasts = ' '.join(_build_forecast_response(forecast_days))

    return current + forecasts


@hook.hook('init', ['locationinit'])
async def location_init(client):
    """Save a user's location to be used for localized weather info"""
    conn = client.bot.dbs[client.server_tag]
    print(('Initializing location column in \'users\''
           f' in /persist/db/{client.server_tag}.db...'))
    db.add_column(conn, 'users', location_column)
    db.ccache()
    print('Location initialization complete.')


@hook.hook('command', ['time', 't', 'weather', 'w'])
async def weather(client, data):
    conn = client.bot.dbs[data.server]
    message = data.split_message
    command = data.command

    apixu_key = _get_apixu_api_key(client)
    if apixu_key == '':
        asyncio.create_task(client.message(data.target,
                                           ('No APIXU appID found. '
                                            'Ask your nearest bot admin to '
                                            'get one and add it into the config.')))
        return

    CURRENT_WEATHER_URL = "https://api.apixu.com/v1/forecast.json?key=" + apixu_key + "&q="


    test_url = ""

    if len(message) > 0:
        if message[0][0] == '@':
            user_to_look_for = message[0][1:]
            
            loc = _get_user_location(conn, location_column, user_to_look_for)
            if loc is None:
                asyncio.create_task(client.message(data.target, "No user/location found."))
                return
            
            test_url = CURRENT_WEATHER_URL + urllib.parse.quote(loc) + "&days=" + str(forecast_days)
        else:
            _update_user_location(conn, location_column, ' '.join(message), data.nickname)
            test_url = CURRENT_WEATHER_URL + urllib.parse.quote(_get_user_location(conn, location_column, data.nickname)) + "&days=" + str(forecast_days)

    else:
        loc = _get_user_location(conn, location_column, data.nickname)
        if loc is None:
            asyncio.create_task(client.message(data.target, "Invalid or unset location."))
            return
        test_url = CURRENT_WEATHER_URL + urllib.parse.quote(_get_user_location(conn, location_column, data.nickname)) + "&days=" + str(forecast_days)

    hdr = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.11 (KHTML, like Gecko) Chrome/23.0.1271.64 Safari/537.11',
       'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
       'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.3',
       'Accept-Encoding': 'none',
       'Accept-Language': 'en-US,en;q=0.8',
       'Connection': 'keep-alive'}

    req = urllib.request.Request(test_url, headers=hdr)
    try:
        weather_info = urllib.request.urlopen(req)
    except urllib.error.HTTPError:
        asyncio.create_task(client.message(data.target, "Invalid or unset location."))
        return

    weather_info = urllib.request.urlopen(req)

    j_weather = json.load(weather_info)
    if command in ['t', 'time']:
        asyncio.create_task(client.message(data.target, _build_time_response(j_weather)))
    elif command in ['w', 'weather']:
        asyncio.create_task(client.message(data.target, _build_weather_response(j_weather)))

    return