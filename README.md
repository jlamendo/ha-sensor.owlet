# ha-sensor.owlet
Owlet Smart Sock v2/v3 Sensor Integration for HomeAssistant using the modern Owlet API.

Credit for getting the new API to work goes to @mbevand for their work in https://github.com/mbevand/owlet_monitor/blob/master/owlet_monitor, which I borrowed from heavily while writing this.

# Installation:
### Manual Install:
Clone this repository, and move the `ha-sensor.owlet/custom_components/owlet` directory into your "custom_components" directory on homeassistant.

 and add the sensor configuration into your configuration.yml.

### HACS Install:

Add this repository as a custom repository in HACS under the type "integration."

### Both:

After installing the integration, you need to enable it by adding the sensor configuration into your configuration.yml - example:
```yaml
sensor:
  - platform: owlet
    username: "owlet_api_email"
    password: !secret owlet_password
    region: "world"
```
And if you want to have individual sensor values for the attributes (e.g. for graphing in grafana via prometheus), you can use value_templates as described below. Each sock's DSN will be embedded in the sensor string (in this case, `ac000w016676179`), so make sure to change that.
```yaml
template:
  sensor:
    - name: "owlet_heart_rate"
      state: "{{states.sensor.owlet_smart_sock_ac000w016676179.attributes.heart_rate}}"
      unit_of_measurement: BPM
    - name: "owlet_spo2"
      state: "{{states.sensor.owlet_smart_sock_ac000w016676179.attributes.oxygen_saturation}}"
      unit_of_measurement: SPO2
    - name: "owlet_movement"
      state: "{{states.sensor.owlet_smart_sock_ac000w016676179.attributes.movement}}"
      unit_of_measurement: '%'
    - name: "owlet_battery"
      state: "{{states.sensor.owlet_smart_sock_ac000w016676179.attributes.battery}}"
      unit_of_measurement: '%'
    - name: "owlet_rssi"
      state: "{{states.sensor.owlet_smart_sock_ac000w016676179.attributes.ble_rssi}}"
      unit_of_measurement: dBm
    - name: "owlet_monitoring_status"
      state: "{{states.sensor.owlet_smart_sock_ac000w016676179.state}}"
```
