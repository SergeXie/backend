import dramatiq
from common.log import log
from dramatiq.brokers.rabbitmq import RabbitmqBroker

# 配置 RabbitMQ broker
rabbitmq_broker = RabbitmqBroker(url="amqp://guest:guest@localhost:5672/")
dramatiq.set_broker(rabbitmq_broker)


@dramatiq.actor
def print_message(message):
    print(f"Received message: {message}")


if __name__ == "__main__":
    print_message.send("Hello, Dramatiq!")
