# Smart Home Automation Ideas

## Current Setup

- 3x Raspberry Pi 4 (living room, bedroom, office)
- Home Assistant on main server
- MQTT for device communication
- Zigbee bridge for smart bulbs

## Project Ideas

### 1. Presence Detection System
Use BLE beacons on keychains to detect which room we're in. Automatically:
- Turn on lights when entering
- Adjust temperature
- Start music in that zone

**Complexity**: Medium
**Cost**: ~$50 for beacons
**Time**: 2-3 weekends

### 2. Voice-Controlled Recipe Assistant
Raspberry Pi in kitchen with speaker/mic. While cooking, can say:
- "What's next?" → Reads next recipe step
- "Set timer 10 minutes"
- "Add milk to shopping list"

**Complexity**: High (need good voice recognition)
**Cost**: ~$80 (speaker + mic)
**Time**: 4-5 weekends

### 3. Plant Watering Monitor
Soil moisture sensors → alert when plants need water. Could automate watering but that feels risky (flooding).

**Complexity**: Low
**Cost**: ~$30 for sensors
**Time**: 1 weekend

## Technical Stack

```python
# Home Assistant automation example
automation:
  - alias: "Bedroom Presence"
    trigger:
      platform: state
      entity_id: sensor.bedroom_beacon
      to: 'home'
    action:
      service: light.turn_on
      entity_id: light.bedroom_main
```

## Notes

The presence detection would be most useful. Current motion sensors have too much latency - by the time they trigger, I've already manually hit the light switch.

#projects #smart-home #raspberry-pi
