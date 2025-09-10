# entities.py

from dataclasses import dataclass, field
from enum import Enum
from queue import Queue
import random
from typing import Optional, Tuple
from uuid import uuid4, UUID
from datetime import datetime
import threading


class TaxiStatus(Enum):
    """Статусы такси"""
    FREE = "free"
    BUSY = "busy"
    ON_WAY = "on_way"
    MOVING_TO_CLIENT = "moving_to_client"
    ON_RIDE = "on_ride"

class ClientStatus(Enum):
    """Статусы клиентов"""
    WAITING = "waiting"
    ON_RIDE = "on_ride"
    ARRIVED = "arrived"
    REFUSED = "refused"


@dataclass
class Taxi:
    """Класс такси с координатами и статусом"""
    id: int
    color: str
    speed: float = field(default_factory=lambda: random.uniform(3.0, 8.0))
    status: TaxiStatus = TaxiStatus.FREE
    location: Tuple[int, int] = (0, 0)
    order: Optional["Order"] = None
    
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    
    def get_location(self) -> Tuple[int, int]:
        with self.lock:
            return self.location
    
    def set_location(self, new_location: Tuple[int, int]) -> None:
        """Безопасное обновление координат"""
        with self.lock:
            self.location = new_location


@dataclass
class Order:
    """Класс заказа на такси"""
    client: "Client"
    from_location: Tuple[int, int]
    to_location: Tuple[int, int]
    taxi: Optional[Taxi] = None
    is_cancelled: bool = False
    uuid: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=datetime.now)
    # Событие для уведомления о назначении такси
    assigned_event: threading.Event = field(default_factory=threading.Event, repr=False)
    
    def cancel(self) -> None:
        """Отмена заказа"""
        self.is_cancelled = True
        if self.taxi:
            with self.taxi.lock:
                self.taxi.status = TaxiStatus.FREE
                self.taxi.order = None
        print(f"Order {self.uuid} cancelled")


@dataclass  
class Client:
    """Класс клиента такси"""
    id: int
    location: Tuple[int, int]
    # Таймаут ожидания в секундах
    patience_timeout: float
    # Текущий активный заказ
    current_order: Optional[Order] = None
    status: ClientStatus = ClientStatus.WAITING
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def set_status(self, new_status: ClientStatus):
        with self.lock:
            self.status = new_status
    
    def place_order(self, to_location: Tuple[int, int], order_queue: Queue[Order]) -> Optional[Order]:
        """Клиент создает заказ и добавляет его в очередь"""
        self.current_order = Order(
            client=self, 
            from_location=self.location, 
            to_location=to_location
        )
        try:
            order_queue.put(self.current_order)
            print(f"Client {self.id} placed order {self.current_order.uuid}")
            return self.current_order
        except Exception as e:
            print(f"Client {self.id} failed to place order: {e}")
            self.current_order = None
            return None
    
    def seet_in_taxi(self):
        self.set_status(ClientStatus.ON_RIDE)
    
    def refused(self):
        self.set_status(ClientStatus.REFUSED)


class DispatcherStatus(Enum):
    """Статусы диспетчера"""
    IDLE = "idle"
    PROCESSING = "processing"
    OFFLINE = "offline"


@dataclass
class Dispatcher:
    """Класс диспетчера"""
    id: int
    status: DispatcherStatus = DispatcherStatus.IDLE
    processed_orders: int = 0
    # Мьютекс для статистики и статуса
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    
    def set_status(self, new_status: DispatcherStatus) -> None:
        """Безопасное обновление статуса"""
        with self.lock:
            self.status = new_status
    
    def increment_processed(self) -> None:
        """Безопасное увеличение счетчика обработанных заказов"""
        with self.lock:
            self.processed_orders += 1