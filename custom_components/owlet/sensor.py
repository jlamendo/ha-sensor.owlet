"""Owlet Smart Sock Sensor integration."""
import logging
import homeassistant.helpers.config_validation as cv

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.entity import Entity
import voluptuous as vol
from dateutil import parser as date


import time, requests, json, datetime

CONF_OWLET_REGION = "region"
SCAN_INTERVAL = datetime.timedelta(seconds=10)
COMPONENT_ICON = "mdi:heart-pulse"
COMPONENT_NAME = "Owlet Smart Sock"


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_OWLET_REGION, default="world"): cv.string,
    }
)

_LOGGER = logging.getLogger(__name__)


class OwletAPI:
    def __init__(self, config):
        """Initialize API Token."""
        self.__client = requests.session()
        self.__JWT = ""
        self.__MINI_TOKEN = ""
        self.__OWLET_USER = config[CONF_USERNAME]
        self.__OWLET_PASS = config[CONF_PASSWORD]
        self.__OWLET_REGION = config[CONF_OWLET_REGION]
        self.__OWLET_TOKEN = None
        self.__OWLET_REGION_CONFIG = {
            "world": {
                "url_mini": "https://ayla-sso.owletdata.com/mini/",
                "url_signin": "https://user-field-1a2039d9.aylanetworks.com/api/v1/token_sign_in",
                "url_base": "https://ads-field-1a2039d9.aylanetworks.com/apiv1",
                "apiKey": "AIzaSyCsDZ8kWxQuLJAMVnmEhEkayH1TSxKXfGA",
                "app_id": "sso-prod-3g-id",
                "app_secret": "sso-prod-UEjtnPCtFfjdwIwxqnC0OipxRFU",
            },
            "europe": {
                "url_mini": "https://ayla-sso.eu.owletdata.com/mini/",
                "url_signin": "https://user-field-eu-1a2039d9.aylanetworks.com/api/v1/token_sign_in",
                "url_base": "https://ads-field-eu-1a2039d9.aylanetworks.com/apiv1",
                "apiKey": "AIzaSyDm6EhV70wudwN3iOSq3vTjtsdGjdFLuuM",
                "app_id": "OwletCare-Android-EU-fw-id",
                "app_secret": "OwletCare-Android-EU-JKupMPBoj_Npce_9a95Pc8Qo0Mw",
            },
        }
        self.__API_KEY = self.__OWLET_REGION_CONFIG[self.__OWLET_REGION]["apiKey"]
        self.__API_URL = self.__OWLET_REGION_CONFIG[self.__OWLET_REGION]["url_base"]
        self.__OWLET_TOKEN_EXPIRE_TIME = None
        self.__OWLET_TOKEN_REAUTH_ATTEMPTS = 0
        self.__OWLET_TOKEN_REAUTH_MAX_ATTEMPTS = 5
        self.__OWLET_TOKEN = self.authenticate()
        self.__devices = None
        self.__token = None

    def authenticate(self, reauthenticate=False):
        _LOGGER.info("Logging into Owlet API via Firebase as %s" % self.__OWLET_USER)
        # authenticate against Firebase, get the JWT.
        # need to pass the X-Android-Package and X-Android-Cert headers because
        # the API key is restricted to the Owlet Android app
        # https://cloud.google.com/docs/authentication/api-keys#api_key_restrictions
        if reauthenticate:
            if (
                self.__OWLET_TOKEN_REAUTH_ATTEMPTS
                <= self.__OWLET_TOKEN_REAUTH_MAX_ATTEMPTS
            ):
                self.__OWLET_TOKEN_REAUTH_ATTEMPTS = (
                    self.__OWLET_TOKEN_REAUTH_ATTEMPTS + 1
                )
                self.__OWLET_TOKEN_REAUTH_RESET_TIMER = time.time() + 1800
            elif time.time() >= self.__OWLET_TOKEN_REAUTH_RESET_TIMER:
                self.__OWLET_TOKEN_REAUTH_ATTEMPTS = 1
            else:
                return self.__OWLET_TOKEN, None
        try:
            r = requests.post(
                f"https://www.googleapis.com/identitytoolkit/v3/relyingparty/verifyPassword?key={self.__API_KEY}",
                data=json.dumps(
                    {
                        "email": self.__OWLET_USER,
                        "password": self.__OWLET_PASS,
                        "returnSecureToken": True,
                    }
                ),
                headers={
                    "X-Android-Package": "com.owletcare.owletcare",
                    "X-Android-Cert": "2A3BC26DB0B8B0792DBE28E6FFDC2598F9B12B74",
                },
            )
            r.raise_for_status()
        except requests.exceptions.RequestException as e:
            _LOGGER.error("Owlet API Could not Authenticate against Firebase: %s" % e)
            return False, e
        self.__JWT = r.json()["idToken"]
        # authenticate against owletdata.com, get the mini_token
        try:
            r = requests.get(
                self.__OWLET_REGION_CONFIG[self.__OWLET_REGION]["url_mini"],
                headers={"Authorization": self.__JWT},
            )
            r.raise_for_status()
        except requests.exceptions.RequestException as e:
            _LOGGER.error(
                "Owlet API Could not Authenticate against owletdata.com: %s" % e
            )
            return False, e
        self.__MINI_TOKEN = r.json()["mini_token"]
        # authenticate against Ayla, get the access_token
        try:
            r = requests.post(
                self.__OWLET_REGION_CONFIG[self.__OWLET_REGION]["url_signin"],
                json={
                    "app_id": self.__OWLET_REGION_CONFIG[self.__OWLET_REGION]["app_id"],
                    "app_secret": self.__OWLET_REGION_CONFIG[self.__OWLET_REGION][
                        "app_secret"
                    ],
                    "provider": "owl_id",
                    "token": self.__MINI_TOKEN,
                },
            )
            r.raise_for_status()
        except requests.exceptions.RequestException as e:
            _LOGGER.error("Owlet API Could not Authenticate against Firebase: %s" % e)
            return False, e
        self.__OWLET_TOKEN = r.json()["access_token"]
        # we will re-auth 60 seconds before the token expires
        self.__OWLET_TOKEN_EXPIRE_TIME = time.time() + r.json()["expires_in"] - 60
        _LOGGER.info("Owlet API Token for %s acquired" % self.__OWLET_USER)
        return self.__OWLET_TOKEN, None

    def api_get(self, route):
        return self.__client.get(
            self.__API_URL + route,
            headers={"Authorization": "auth_token " + self.__OWLET_TOKEN},
        )

    def api_post(self, route, json_body):
        return self.__client.post(
            self.__API_URL + route,
            json=json_body,
            headers={"Authorization": "auth_token " + self.__OWLET_TOKEN},
        )

    @property
    def token(self):
        if (
            (self.__OWLET_TOKEN is None)
            or (self.__OWLET_TOKEN_EXPIRE_TIME is None)
            or (time.time() >= self.__OWLET_TOKEN_EXPIRE_TIME)
        ):
            return False
        return True

    def get_devices(self):
        try:
            _LOGGER.info("Getting list of Owlet Devices")
            r = self.api_get("/devices.json")
            r.raise_for_status()
        except requests.exceptions.RequestException as e:
            _LOGGER.error("Owlet Network error while retrieving devices: %s" % e)
            time.sleep(5)
            self.__client = requests.session()
            return []
        self.__devices = r.json()
        self.__device_serial_numbers = []
        if len(self.__devices) < 1:
            _LOGGER.info("No Owlet Smart Sock Found")
        # Allow for multiple devices
        else:
            for device in self.__devices:
                if device["device"]["dsn"] not in self.__device_serial_numbers:
                    self.__device_serial_numbers.append(device["device"]["dsn"])
                    _LOGGER.info(
                        "Found Owlet Smart Sock with Serial Number %s"
                        % device["device"]["dsn"]
                    )
        return self.__device_serial_numbers

    @property
    def devices(self):
        if self.__devices is None or self.__device_serial_numbers is None:
            self.get_devices()
        return self.__device_serial_numbers

    def activate_sock(self, dsn):
        try:
            r = self.api_post(
                "/dsns/%s/properties/APP_ACTIVE/datapoints.json" % dsn,
                {"datapoint": {"metadata": {}, "value": 1}},
            )
            r.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            _LOGGER.error("Owlet Network error while activating Sock %s: %s" % (dsn, e))
            time.sleep(5)
            self.__client = requests.session()
            return False

    def sock_properties(self, dsn):
        if self.activate_sock(dsn):
            device_props = {"DSN": dsn}
            try:
                r = self.api_get("/dsns/%s/properties.json" % dsn)
                timestamp = datetime.date.today().isoformat()
                r.raise_for_status()
            except requests.exceptions.RequestException as e:
                _LOGGER.error(
                    "Owlet Network error while retrieving data for Sock %s: %s"
                    % (dsn, e)
                )
                time.sleep(5)
                self.__client = requests.session()
                return False, False
            response_body = r.json()
            _LOGGER.debug("OWLET: %s" % json.dumps(r.json()))
            for prop in response_body:
                device_props[prop["property"]["name"]] = prop["property"]
            return device_props, timestamp
        else:
            return False, False

    def vitals(self, dsn):
        p, timestamp = self.sock_properties(dsn)
        if p is not False:
            if "REAL_TIME_VITALS" in p:
                # Sock is a Smart Sock 3
                rt_vitals = json.loads(p["REAL_TIME_VITALS"]["value"])
                return {
                    "dsn": p["DSN"],
                    "charge_status": rt_vitals["chg"],
                    "heart_rate": "%d" % rt_vitals["hr"],
                    "base_station_on": rt_vitals["bso"],
                    "oxygen_saturation": "%d" % rt_vitals["ox"],
                    "movement": "%d" % rt_vitals["mv"],
                    "battery": "%d" % rt_vitals["bat"],
                    "ble_rssi": "%d" % rt_vitals["rsi"],
                    "LOW_INTEG_READ": bool(p["LOW_INTEG_READ"]["value"]),
                    "LOW_BATT_ALRT": bool(p["LOW_BATT_ALRT"]["value"]),
                    "HIGH_HR_ALRT": bool(p["HIGH_HR_ALRT"]["value"]),
                    "LOW_HR_ALRT": bool(p["LOW_HR_ALRT"]["value"]),
                    "LOW_OX_ALRT": bool(p["LOW_OX_ALRT"]["value"]),
                    "DISCOMFORT_ALRT": bool(p.get("DISCOMFORT_ALRT",{"value":0})["value"]),
                    "SOCK_DISCON_ALRT": bool(p["SOCK_DISCON_ALRT"]["value"]),
                    "PREVIEW_LOW_PRIORITY_ALARM": bool(p["PREVIEW_LOW_PRIORITY_ALARM"]["value"]),
                    "PREVIEW_HIGH_PRIORITY_ALARM": bool(p["PREVIEW_HIGH_PRIORITY_ALARM"]["value"]),
                    "PREVIEW_MED_PRIORITY_ALARM": bool(p["PREVIEW_MED_PRIORITY_ALARM"]["value"]),
                    "RED_ALERT_SUMMARY": "%s" % p["RED_ALERT_SUMMARY"]["value"],
                    "ts": date.parse(p["REAL_TIME_VITALS"]["data_updated_at"]),
#                    "rt_vitals": rt_vitals,
                    "error": False,
                }, p
            elif "CHARGE_STATUS" in p:
                # Sock is a Smart Sock 2
                return {
                    "dsn": p["DSN"],
                    "charge_status": p["CHARGE_STATUS"]["value"],
                    "heart_rate": "%d" % p["HEART_RATE"]["value"],
                    "base_station_on": p["BASE_STATION_ON"]["value"],
                    "oxygen_saturation": "%d" % p["OXYGEN_LEVEL"]["value"],
                    "movement": "%d" % p["MOVEMENT"]["value"],
                    "battery": "%d" % p["BATT_LEVEL"]["value"],
                    "ble_rssi": "%d" % p["BLE_RSSI"]["value"],
                    "LOW_INTEG_READ": bool(p["LOW_INTEG_READ"]["value"]),
                    "LOW_BATT_ALRT": bool(p["LOW_BATT_ALRT"]["value"]),
                    "HIGH_HR_ALRT": bool(p["HIGH_HR_ALRT"]["value"]),
                    "LOW_HR_ALRT": bool(p["LOW_HR_ALRT"]["value"]),
                    "LOW_OX_ALRT": bool(p["LOW_OX_ALRT"]["value"]),
                    "SOCK_DISCON_ALRT": bool(p["SOCK_DISCON_ALRT"]["value"]),
                    "RED_ALERT_SUMMARY": "",
                    "error": False,
                }, p
        return {"dsn": dsn, "error": True}, p


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the sensor platform."""
    Owlet = OwletAPI(config)

    if not Owlet.authenticate():
        _LOGGER.error("Unable to get Owlet API Token")
        return
    for SmartSockDSN in Owlet.devices:
        _LOGGER.info("Adding Owlet Smart Sock %s" % SmartSockDSN)
        add_entities([OwletSmartSock(SmartSockDSN, Owlet)], True)


class OwletSmartSock(Entity):
    """An Owlet Smart Sock Sensor."""

    def __init__(self, DSN, Owlet):
        """Initialize the Smart Sock Sensor."""
        self.__DSN = DSN
        self.__Owlet = Owlet
        self.__state = None
        self.__attributes = None
        self._setup_state()
        self._setup_attributes()

    @property
    def name(self):
        """Return the name of the sensor."""
        return "Owlet Smart Sock %s" % self.__DSN

    @property
    def state(self):
        """Return the Socks Currently Measured Vitals."""
        return self.__state

    @property
    def extra_state_attributes(self):
        """Return device specific state attributes."""
        return self.__attributes

    def _setup_state(self):
        self.__state = "Disconnected"

    def _setup_attributes(self):
        self.__attributes = {
            "dsn": self.__DSN,
            "charge_status": None,
            "heart_rate": None,
            "base_station_on": None,
            "oxygen_saturation": None,
            "movement": None,
            "battery": None,
            "ble_rssi": None,
            "active": False,
            "alarm": None,
            "alerts": None,
#            "raw_json": None,
            "rt_vitals": {},
            "ts": None
        }

    def _clr(self, state):
        self.__tmp_attributes = {
            "dsn": self.__DSN,
            "charge_status": None,
            "heart_rate": None,
            "base_station_on": None,
            "oxygen_saturation": None,
            "movement": None,
            "battery": None,
            "ble_rssi": None,
            "active": False,
            "alarm": None,
            "alerts": None,
#            "raw_json": None,
            "rt_vitals": {},
            "ts": None
            
        }
        self.__state = state


    def _set_state(self, state=False, attrs=False):
        if not attrs:
            attrs = ["dsn", "heart_rate", "charge_status", "base_station_on", "ts", "rt_vitals", "oxygen_saturation", "movement", "battery", "ble_rssi"]#, "LOW_INTEG_READ", "LOW_BATT_ALRT", "HIGH_HR_ALRT", "LOW_HR_ALRT", "LOW_OX_ALRT", "SOCK_DISCON_ALRT"]
        if not self.__tmp_attributes or "dsn" not in self.__tmp_attributes:
            self.__tmp_attributes = self.__attributes
        if state:
            for attr in (k for k in attrs if k in state):
                self.__tmp_attributes[attr] = state[attr]
            tmp_alarm_active = False
            for k in ["LOW","MED","HIGH"]:
                if "PREVIEW_" + k + "_PRIORITY_ALARM" in state and int(state["PREVIEW_" + k + "_PRIORITY_ALARM" ]) == 1:
                    self.__tmp_attributes["alarm"] = k
                    tmp_alarm_active = True
            if not tmp_alarm_active:
                self.__tmp_attributes["alarm"] = None
            tmp_active_alerts = ""
            for k in ["LOW_INTEG_READ","LOW_BATT_ALRT","HIGH_HR_ALRT","LOW_HR_ALRT", "LOW_OX_ALRT", "SOCK_DISCON_ALRT","DISCOMFORT_ALRT"]:
                if  k  in state and int(state[k]) == 1:
                    tmp_active_alerts = tmp_active_alerts + k + ","
            if len(tmp_active_alerts) > 0:
                self.__tmp_attributes["alerts"] = tmp_active_alerts.rstrip(',')

        self.__attributes = self.__tmp_attributes
        self.__tmp_attributes = {}

    def update(self):
        """Fetch latest vital signs from the Owlet API"""
        # States = ["Monitoring", "Charging", "Charged", "LOW_INTEG_READ", "Disconnected", "Error"]
        if self.__state == "Error":
            self.__Owlet.authenticate(True)
        elif self.__state == "Disconnected":
            self.__Owlet.authenticate(True)

        if not self.__Owlet.token:
            self.__Owlet.authenticate()

    
        state, raw_json = self.__Owlet.vitals(self.__DSN)
        # If we get an error, just flag it and exit

        if state["error"] != False:
            self._clr("Error")
            self._set_state()
            self.__attributes["active"] = False
        else:
            bpm_integ = bool("heart_rate" in state and int(state["heart_rate"]) > 0 and not bool(state["LOW_HR_ALRT"]))
            spo2_integ = bool("oxygen_saturation" in state and int(state["oxygen_saturation"]) > 0 and not bool(state["LOW_OX_ALRT"]))
            # Truth table for detecting "yellow alerts" - aka sock is connected, powered on, but has no signal.
            #   LIR      bpm   sp02         low_read_integ
            #    0 OR 1 ( 0 NOR 0 = 1 )    = 1  // No LIR, No HR + Not LowHR Alert or No SPO2 + Not LowOX Alert = LIR. If there's no ox/bpm alerts, but they are both zero, we can conclude the sensor can't get a read even w/o the integ alert.
            #    0 OR 0 ( 0 NOR 1 = 0 )    = 0  // No LIR, And only one of HR/OX is low. If this is the case, the sensor is reading one of the measurements but the other is 0, something fishy is going on other than integrity. We want to not mark this as LIR, so that alerts can fire if need be.
            #    0 OR 0 ( 1 NOR 0 = 0 )    = 0  // No LIR, And only one of HR/OX is low. If this is the case, the sensor is reading one of the measurements but the other is 0, something fishy is going on other than integrity. We want to not mark this as LIR, so that alerts can fire if need be.
            #    0 OR 0 ( 1 NOR 1 = 0 )    = 0  // Good state - good readings from everything.
            #    1 OR 1 ( 0 NOR 0 = 1 )    = 1  // All readings are bad - a clear case of no signal.
            #    1 OR 0 ( 0 NOR 1 = 0 )    = 1  // LIR alert is firing, but only one reading is bad. Unlikely to ever happen, but if it does, trust owlet and mark it as no signal
            #    1 OR 0 ( 1 NOR 0 = 0 )    = 1  // LIR alert is firing, but only one reading is bad. Unlikely to ever happen, but if it does, trust owlet and mark it as no signal
            #    1 OR 0 ( 1 NOR 1 = 0 )    = 1  // LIR alert is firing, but both signals are good. Shouldn't ever happen, if it does, trust the owlet.
            LIR = bool("LOW_INTEG_READ" in state and bool(state["LOW_INTEG_READ"]) or (not bpm_integ and not spo2_integ))
            
            # Regardless of what base_station_on says, the vitals are king here. If we're getting readings, let them through. Might need to be tuned later.
            base_station_dc = bool(("base_station_on" in state and int(state["base_station_on"]) != 1) and LIR)

            if base_station_dc:
                self._clr("Disconnected")
                self._set_state(state, ["charge_status", "base_station_on"])
                self.__attributes["active"] = False
            elif LIR:
                if "charge_status" in state and int(state["charge_status"]) == 1:
                    self._clr("Charging")
                    self._set_state(state, ["charge_status", "base_station_on"])
                elif "charge_status" in state and int(state["charge_status"]) == 2:
                    self._clr("Charged")
                    self._set_state(state, ["charge_status", "base_station_on"])
                else:
                    self._clr("LOW_INTEG_READ")
                    self._set_state(state, ["charge_status", "base_station_on", "battery", "ble_rssi"])
            else:
                self._clr("Monitoring")
                self._set_state(state)
                _LOGGER.debug("OWLET_STATE: %s" % state)
                _LOGGER.debug("OWLET_attributes: %s" % self.__attributes)
                self.__attributes["active"] = True
#        self.__attributes["raw_json"] = raw_json
        
