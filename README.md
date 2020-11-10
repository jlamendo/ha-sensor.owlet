# ha-sensor.owlet
Owlet Smart Sock v2/v3 Sensor Integration for HomeAssistant using the modern Owlet API.

# Installation:
Clone this repository into your "custom_components" directory on homeassistant, and add the sensor configuration into your configuration.yml.

Example:
```yaml
sensor:
  - platform: owlet
    username: "owlet_api_email"
    password: !secret owlet_password
    region: "world"
```
And if you want to have individual sensor values for the attributes, e.g. for graphing in grafana via prometheus, you can use value_templates:
```yaml
- platform: template
  sensors:
    owlet_heart_rate:
      value_template: "{{states.sensor.owlet_smart_sock_[YOUR_SMART_SOCK_SERIAL_NUMBER].attributes.heart_rate}}"
      unit_of_measurement: BPM
    owlet_spo2:
      value_template: "{{states.sensor.owlet_smart_sock_[YOUR_SMART_SOCK_SERIAL_NUMBER].attributes.oxygen_saturation}}"
      unit_of_measurement: SPO2
    owlet_movement:
      value_template: "{{states.sensor.owlet_smart_sock_[YOUR_SMART_SOCK_SERIAL_NUMBER].attributes.movement}}"
      unit_of_measurement: '%'
    owlet_battery:
      value_template: "{{states.sensor.owlet_smart_sock_[YOUR_SMART_SOCK_SERIAL_NUMBER].attributes.battery}}"
      unit_of_measurement: '%'
    owlet_rssi:
      value_template: "{{states.sensor.owlet_smart_sock_[YOUR_SMART_SOCK_SERIAL_NUMBER].attributes.ble_rssi}}"
      unit_of_measurement: dBm
    owlet_monitoring_status:
      value_template: "{{states.sensor.owlet_smart_sock_[YOUR_SMART_SOCK_SERIAL_NUMBER].attributes.ble_rssi}}"
      unit_of_measurement: dBm
```
