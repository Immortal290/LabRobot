import asyncio
import json
import logging
from typing import Optional, Callable, Dict
import aiomqtt

from app.core.config import settings

logger = logging.getLogger(__name__)

class RobotMQTTClient:
    def __init__(self):
        self.client: Optional[aiomqtt.Client] = None
        self._task: Optional[asyncio.Task] = None
        self._message_callbacks: Dict[str, Callable] = {}

    async def connect(self):
        try:
            self.client = aiomqtt.Client(
                hostname=settings.MQTT_BROKER,
                port=settings.MQTT_PORT,
                username=settings.MQTT_USERNAME or None,
                password=settings.MQTT_PASSWORD or None
            )
            await self.client.connect()
            logger.info(f"Connected to MQTT broker at {settings.MQTT_BROKER}:{settings.MQTT_PORT}")
            
            await self.client.subscribe("robot/+/status")
            await self.client.subscribe("robot/+/heartbeat")
            await self.client.subscribe("robot/+/ack")
            await self.client.subscribe("robot/+/error")
            
            self._task = asyncio.create_task(self._listen())
        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {e}")

    async def disconnect(self):
        if self._task:
            self._task.cancel()
        if self.client:
            await self.client.disconnect()
            logger.info("Disconnected from MQTT broker")

    def register_callback(self, topic_suffix: str, callback: Callable):
        self._message_callbacks[topic_suffix] = callback

    async def _listen(self):
        if not self.client:
            return
            
        try:
            async for message in self.client.messages:
                topic = str(message.topic)
                payload = message.payload.decode()
                
                try:
                    data = json.loads(payload)
                    parts = topic.split('/')
                    if len(parts) >= 3:
                        suffix = parts[2]
                        if suffix in self._message_callbacks:
                            asyncio.create_task(self._message_callbacks[suffix](parts[1], data))
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON received on {topic}: {payload}")
                except Exception as e:
                    logger.error(f"Error processing MQTT message on {topic}: {e}")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"MQTT listener error: {e}")

    async def publish_command(self, robot_id: str, command: dict):
        if not self.client:
            logger.error("MQTT client not connected. Cannot send command.")
            return False
            
        topic = f"robot/{robot_id}/command"
        payload = json.dumps(command)
        try:
            await self.client.publish(topic, payload, qos=1)
            logger.info(f"Published to {topic}: {command.get('command')}")
            return True
        except Exception as e:
            logger.error(f"Failed to publish to {topic}: {e}")
            return False

mqtt_client = RobotMQTTClient()
