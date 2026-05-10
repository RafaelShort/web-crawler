import hashlib
import math
from bitarray import bitarray
from loguru import logger


class BloomFilter:
    """
    Estrutura de dados probabilística para deduplicação eficiente de URLs.
    """

    def __init__(self, capacity: int = 1_000_000, error_rate: float = 0.01):
        """
        Args:
            capacity:   número máximo esperado de URLs únicas
            error_rate: taxa aceitável de falsos positivos (0.01 = 1%)
        """
        self.capacity = capacity
        self.error_rate = error_rate

        # Calcular tamanho ideal do bit array
        # Fórmula: m = -(n * ln(p)) / (ln(2)^2)
        self.size = self._optimal_size(capacity, error_rate)

        # Calcular número ideal de funções hash 
        # Fórmula: k = (m/n) * ln(2)
        self.hash_count = self._optimal_hash_count(self.size, capacity)

        # Inicializar bit array com zeros
        self.bit_array = bitarray(self.size)
        self.bit_array.setall(0)

        # Contador de itens inseridos
        self._count = 0

        logger.info(
            f"BloomFilter inicializado | "
            f"capacity={capacity:,} | "
            f"error_rate={error_rate:.1%} | "
            f"size={self.size:,} bits ({self.size / 8 / 1024:.1f} KB) | "
            f"hash_count={self.hash_count}"
        )

    # Funções de cálculo

    @staticmethod
    def _optimal_size(n: int, p: float) -> int:
        """Calcula o tamanho ideal do bit array."""
        m = -(n * math.log(p)) / (math.log(2) ** 2)
        return int(m)

    @staticmethod
    def _optimal_hash_count(m: int, n: int) -> int:
        """Calcula o número ideal de funções hash."""
        k = (m / n) * math.log(2)
        return int(k)

    # Geração de posições hash

    def _hash_positions(self, item: str) -> list[int]:
        """
        Gera k posições no bit array para um item.
        Usa double hashing para simular k funções hash independentes.
        """
        positions = []
        item_bytes = item.encode("utf-8")

        h1 = int(hashlib.md5(item_bytes).hexdigest(), 16)
        h2 = int(hashlib.sha256(item_bytes).hexdigest(), 16)

        for i in range(self.hash_count):
            # Double hashing: h(i) = (h1 + i * h2) mod m
            position = (h1 + i * h2) % self.size
            positions.append(position)

        return positions

    # Interface pública

    def add(self, item: str) -> None:
        """Adiciona um item ao filtro."""
        for position in self._hash_positions(item):
            self.bit_array[position] = 1
        self._count += 1

    def contains(self, item: str) -> bool:
        """
        Verifica se um item provavelmente já foi visto.
        """
        return all(
            self.bit_array[position]
            for position in self._hash_positions(item)
        )

    def __contains__(self, item: str) -> bool:
        """Permite uso com operador 'in': if url in bloom_filter."""
        return self.contains(item)

    def __len__(self) -> int:
        """Retorna o número de itens inseridos."""
        return self._count

    @property
    def fill_ratio(self) -> float:
        """Percentual do bit array preenchido."""
        return self.bit_array.count(1) / self.size

    def stats(self) -> dict:
        """Retorna estatísticas do filtro."""
        return {
            "capacity": self.capacity,
            "inserted": self._count,
            "size_bits": self.size,
            "size_kb": round(self.size / 8 / 1024, 2),
            "hash_count": self.hash_count,
            "fill_ratio": round(self.fill_ratio, 4),
            "error_rate": self.error_rate,
        }
