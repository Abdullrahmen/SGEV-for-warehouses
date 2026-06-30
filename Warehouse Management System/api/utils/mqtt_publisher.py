import json
import threading
import logging
import paho.mqtt.client as mqtt
from decouple import config

logger = logging.getLogger("api")


class MQTTPublisher:
    _client = None
    _lock = threading.Lock()

    @classmethod
    def get_client(cls):
        with cls._lock:
            if cls._client is None or not cls._client.is_connected():
                cls._client = mqtt.Client()
                cls._client.username_pw_set(
                    config("MQTT_USERNAME"), config("MQTT_PASSWORD")
                )
                cls._client.connect(
                    config("MQTT_BROKER_HOST", default="localhost"),
                    config("MQTT_BROKER_PORT", default=1883, cast=int),
                )
                cls._client.loop_start()
                logger.info("MQTTPublisher connected to broker")
            return cls._client

    @classmethod
    def publish(cls, topic, payload, qos=1, retain=False):
        client = cls.get_client()
        if isinstance(payload, (dict, list)):
            payload = json.dumps(payload)
        result = client.publish(topic, payload, qos=qos, retain=retain)
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            logger.error(f"MQTT publish failed to {topic}: {result.rc}")
        return result
