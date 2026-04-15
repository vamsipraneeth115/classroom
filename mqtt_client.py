from __future__ import annotations

from dataclasses import dataclass

import paho.mqtt.client as mqtt


@dataclass
class MQTTConfig:
    broker_host: str = "localhost"
    broker_port: int = 1883
    topic: str = "classroom/alert"
    client_id: str = "classroom-analyzer"


class SimulatedAlertPublisher:
    def publish_state(self, state: str) -> None:
        if state in {"sleepy", "distracted"}:
            print(f"LED ON ({state})")
        else:
            print("LED OFF (attentive)")

    def close(self) -> None:
        return None


class MQTTAlertPublisher:
    def __init__(self, config: MQTTConfig) -> None:
        self.config = config
        self.client = mqtt.Client(client_id=config.client_id)
        self.client.connect(config.broker_host, config.broker_port, 60)
        self.client.loop_start()

    def publish_state(self, state: str) -> None:
        self.client.publish(self.config.topic, state, qos=1)
        if state in {"sleepy", "distracted"}:
            print(f"LED ON ({state})")
        else:
            print("LED OFF (attentive)")

    def close(self) -> None:
        self.client.loop_stop()
        self.client.disconnect()


def build_publisher(mode: str, config: MQTTConfig | None = None):
    if mode == "real":
        return MQTTAlertPublisher(config or MQTTConfig())
    return SimulatedAlertPublisher()
