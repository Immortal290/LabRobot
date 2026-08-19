# AURA Robot Delivery Protocol

This document outlines the MQTT-based communication protocol between the web application (Backend API) and the AURA delivery robot (ROS 2 / Raspberry Pi).

## MQTT Broker Requirements

- **Broker**: Standard MQTT 3.1.1 or 5.0 (e.g., Mosquitto).
- **Authentication**: Depending on environment (TLS and auth configurable via environment variables).

## Topic Structure

The backend communicates with robots using topics structured as follows:

- `robot/{robot_id}/command` - Backend publishes commands here. Robot subscribes.
- `robot/{robot_id}/status` - Robot publishes status updates here. Backend subscribes.
- `robot/{robot_id}/heartbeat` - Robot publishes periodic heartbeats (e.g. every 5s). Backend subscribes.
- `robot/{robot_id}/ack` - Robot publishes command acknowledgements here. Backend subscribes.
- `robot/{robot_id}/error` - Robot publishes error events here. Backend subscribes.

Example for `ROBOT_01`:
- `robot/ROBOT_01/command`
- `robot/ROBOT_01/status`

## JSON Schemas

### 1. Delivery Command (`robot/{robot_id}/command`)

When an order is approved and dispatched, the backend sends a `DELIVER` command.

```json
{
  "protocol_version": "1.0",
  "command": "DELIVER",
  "command_id": "8f3a5b29-c89b-4a5c-941f-df73c38b248a",
  "order_id": "ORD_10024",
  "robot_id": "ROBOT_01",
  "destination": {
    "location_id": "desk1",
    "x": -1.530,
    "y": 0.808,
    "yaw": 0.0
  },
  "items": []
}
```

### 2. Compartment Control Command (`robot/{robot_id}/command`)

When the user enters the correct OTP on the web app or kiosk:

```json
{
  "protocol_version": "1.0",
  "command": "UNLOCK_COMPARTMENT",
  "command_id": "1b3a5b29-a89b-4a5c-941f-df73c38b248b",
  "order_id": "ORD_10024",
  "robot_id": "ROBOT_01",
  "compartment": "COMPARTMENT_1"
}
```

Other supported commands:
- `CANCEL_DELIVERY`
- `PAUSE`
- `RESUME`
- `RETURN_TO_BASE`
- `EMERGENCY_STOP`

### 3. Robot Status (`robot/{robot_id}/status`)

The robot must publish its state changes as it moves through the delivery pipeline.

```json
{
  "protocol_version": "1.0",
  "robot_id": "ROBOT_01",
  "order_id": "ORD_10024",
  "status": "NAVIGATING",
  "timestamp": "2026-08-19T10:00:00Z"
}
```

**Supported Statuses (State Machine):**
- `IDLE`
- `ASSIGNED`
- `NAVIGATING`
- `ARRIVED`
- `COMPARTMENT_OPEN`
- `ITEM_COLLECTED`
- `RETURNING`
- `DELIVERY_COMPLETED`
- `PAUSED`
- `ERROR`
- `NAVIGATION_FAILED`
- `EMERGENCY_STOP`

*Note: The backend handles `WAITING_FOR_OTP` and `OTP_VERIFIED` internally.*

### 4. Heartbeat (`robot/{robot_id}/heartbeat`)

Published every 5-10 seconds by the robot to indicate it is online.

```json
{
  "robot_id": "ROBOT_01",
  "status": "ONLINE",
  "battery": 87.5,
  "timestamp": "2026-08-19T10:05:00Z"
}
```

If the backend does not receive a heartbeat for a configurable threshold (e.g. 30 seconds), the robot is marked as `OFFLINE`.
