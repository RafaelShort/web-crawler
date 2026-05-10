import json
import asyncio
import aio_pika
from dataclasses import dataclass
from loguru import logger

from src.config import get_settings


@dataclass
class CrawlMessage:
    """Mensagem que trafega pela fila do RabbitMQ."""
    url: str
    depth: int = 0
    retries: int = 0
    source_url: str = ""

    def to_json(self) -> str:
        return json.dumps({
            "url": self.url,
            "depth": self.depth,
            "retries": self.retries,
            "source_url": self.source_url,
        })

    @staticmethod
    def from_json(data: str) -> "CrawlMessage":
        obj = json.loads(data)
        return CrawlMessage(
            url=obj["url"],
            depth=obj.get("depth", 0),
            retries=obj.get("retries", 0),
            source_url=obj.get("source_url", ""),
        )


class QueueManager:
    """
    Responsável por gerenciar a fila de URLs no RabbitMQ.

    Funcionalidades:
    - Publicar URLs para crawling
    - Consumir URLs da fila
    - Dead Letter Queue para mensagens com falha
    - Confirmação de processamento (ack/nack)
    """

    def __init__(self):
        settings = get_settings()
        self.uri = settings.rabbitmq_uri
        self.queue_name = settings.rabbitmq_queue
        self.dead_letter_queue = f"{settings.rabbitmq_queue}_dead"

        self._connection: aio_pika.RobustConnection | None = None
        self._channel: aio_pika.Channel | None = None
        self._queue: aio_pika.Queue | None = None

        # ── Estatísticas ──────────────────────────────────────
        self._published = 0
        self._consumed = 0
        self._acked = 0
        self._nacked = 0

    # ── Conexão ───────────────────────────────────────────────────────────────

    async def connect(self) -> None:
        """Conecta ao RabbitMQ e declara as filas."""
        self._connection = await aio_pika.connect_robust(self.uri)
        self._channel = await self._connection.channel()

        # ── Prefetch: processar 1 mensagem por vez por worker ─
        await self._channel.set_qos(prefetch_count=1)

        # ── Dead Letter Queue ──────────────────────────────────
        await self._channel.declare_queue(
            self.dead_letter_queue,
            durable=True,
        )

        # ── Fila principal ─────────────────────────────────────
        self._queue = await self._channel.declare_queue(
            self.queue_name,
            durable=True,
            arguments={
                "x-dead-letter-exchange": "",
                "x-dead-letter-routing-key": self.dead_letter_queue,
                "x-message-ttl": 3_600_000,  # 1 hora
            },
        )

        logger.info(
            f"RabbitMQ conectado | "
            f"queue={self.queue_name} | "
            f"dlq={self.dead_letter_queue}"
        )

    async def disconnect(self) -> None:
        """Fecha a conexão com o RabbitMQ."""
        if self._connection:
            await self._connection.close()
            logger.info("RabbitMQ desconectado")

    # ── Publicar ──────────────────────────────────────────────────────────────

    async def publish(self, message: CrawlMessage) -> None:
        """Publica uma URL na fila para crawling."""
        if not self._channel:
            raise RuntimeError("QueueManager não conectado. Chame connect() primeiro.")

        body = message.to_json().encode()

        await self._channel.default_exchange.publish(
            aio_pika.Message(
                body=body,
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,  # sobrevive a restart
            ),
            routing_key=self.queue_name,
        )

        self._published += 1
        logger.debug(f"📤 Publicado: {message.url} (depth={message.depth})")

    async def publish_many(self, urls: list[str], depth: int = 0, source_url: str = "") -> None:
        """Publica múltiplas URLs na fila."""
        for url in urls:
            await self.publish(CrawlMessage(
                url=url,
                depth=depth,
                source_url=source_url,
            ))
        logger.info(f"📤 {len(urls)} URLs publicadas na fila")

    # ── Consumir ──────────────────────────────────────────────────────────────

    async def consume(self, callback) -> None:
        """
        Consome mensagens da fila e chama o callback para cada uma.

        Args:
            callback: função assíncrona que recebe um CrawlMessage
                      deve retornar True para ack, False para nack
        """
        if not self._queue:
            raise RuntimeError("QueueManager não conectado. Chame connect() primeiro.")

        logger.info(f"Aguardando mensagens na fila: {self.queue_name}")

        async with self._queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process(requeue=False):
                    try:
                        crawl_msg = CrawlMessage.from_json(message.body.decode())
                        self._consumed += 1

                        success = await callback(crawl_msg)

                        if success:
                            self._acked += 1
                        else:
                            self._nacked += 1

                    except Exception as e:
                        self._nacked += 1
                        logger.error(f"Erro ao processar mensagem: {e}")

    # ── Utilitários ───────────────────────────────────────────────────────────

    async def get_queue_size(self) -> int:
        """Retorna o número de mensagens na fila."""
        if not self._channel:
            return 0

        queue = await self._channel.declare_queue(
            self.queue_name,
            passive=True,   # apenas consulta, não cria
        )
        return queue.declaration_result.message_count

    # ── Estatísticas ──────────────────────────────────────────────────────────

    def stats(self) -> dict:
        return {
            "published": self._published,
            "consumed": self._consumed,
            "acked": self._acked,
            "nacked": self._nacked,
        }
