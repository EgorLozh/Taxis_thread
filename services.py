# services.py

import threading
import time
import math
from queue import Queue, Empty
from typing import List, Tuple, Optional
from entities import Taxi, TaxiStatus, Order, Dispatcher, DispatcherStatus, Client


class GeometryUtils:
    """Утилиты для геометрических вычислений"""
    
    @staticmethod
    def calculate_distance(point_a: Tuple[int, int], point_b: Tuple[int, int]) -> float:
        """Вычисляет евклидово расстояние между двумя точками."""
        return (point_b[0] - point_a[0]) + (point_b[1] - point_a[1])
    
    @staticmethod
    def calculate_movement_steps(start: Tuple[int, int], end: Tuple[int, int], speed: float) -> int:
        """Рассчитывает количество шагов для перемещения с учетом скорости."""
        distance = GeometryUtils.calculate_distance(start, end)
        return max(1, int(distance / speed))


class TaxiService:
    """Сервис для управления такси и поездками"""
    
    def __init__(self, taxis: List[Taxi]):
        self.taxis = taxis
        self.is_running = True
    
    def find_nearest_taxi(self, target_location: Tuple[int, int]) -> Optional[Taxi]:
        """Находит ближайшее свободное такси к целевой точке."""
        nearest_taxi = None
        min_distance = float('inf')

        for taxi in self.taxis:
            with taxi.lock:
                if taxi.status == TaxiStatus.FREE:
                    distance = GeometryUtils.calculate_distance(taxi.location, target_location)
                    if distance < min_distance:
                        min_distance = distance
                        nearest_taxi = taxi
        return nearest_taxi

    def simulate_ride(self, taxi: Taxi, order: Order):
        """Симулирует поездку такси: к клиенту -> к точке назначения"""
        try:
            # 1. Едем к клиенту
            taxi.status = TaxiStatus.MOVING_TO_CLIENT
            print(f"Taxi {taxi.id} moving to client at {order.from_location} (speed: {taxi.speed})")
            
            self._move_taxi_to_target(taxi, order.from_location)
            
            # 2. Забираем клиента
            with taxi.lock:
                taxi.status = TaxiStatus.ON_RIDE
            print(f"Taxi {taxi.id} picked up client {order.client.id}")
            
            # 3. Едем к точке назначения
            self._move_taxi_to_target(taxi, order.to_location)
            
            # 4. Завершаем поездку
            with taxi.lock:
                taxi.status = TaxiStatus.FREE
                taxi.order = None
                order.taxi = None
            print(f"Taxi {taxi.id} completed order {order.uuid}")
            
        except Exception as e:
            print(f"Error in taxi {taxi.id} simulation: {e}")
            with taxi.lock:
                taxi.status = TaxiStatus.FREE
                taxi.order = None

    def _move_taxi_to_target(self, taxi: Taxi, target: Tuple[int, int]):
        """Плавное перемещение такси к цели с учетом его скорости"""
        current_location = taxi.get_location()
        steps = GeometryUtils.calculate_movement_steps(current_location, target, taxi.speed)
        
        if steps <= 0:
            taxi.set_location(target)
            return
            
        current_x, current_y = current_location
        target_x, target_y = target
        
        dx = target_x - current_x
        dy = target_y - current_y
        
        for step in range(steps):
            if not self.is_running:
                break
                
            progress = (step + 1) / steps
            new_x = current_x + dx * progress
            new_y = current_y + dy * progress
            
            taxi.set_location((int(new_x), int(new_y)))
            time.sleep(0.1)  # Замедляем для наглядности

    def stop(self):
        """Останавливает все операции такси"""
        self.is_running = False


class DispatcherService:
    """Сервис для управления диспетчерами"""
    
    def __init__(self, dispatchers: List[Dispatcher], order_queue: Queue, taxi_service: TaxiService):
        self.dispatchers = dispatchers
        self.order_queue = order_queue
        self.taxi_service = taxi_service
        self.is_running = False
        self.threads = []
    
    def start(self):
        """Запускает всех диспетчеров"""
        self.is_running = True
        self.threads = []
        
        for dispatcher in self.dispatchers:
            thread = threading.Thread(
                target=self._dispatcher_worker,
                args=(dispatcher,),
                daemon=True,
                name=f"Dispatcher-{dispatcher.id}"
            )
            thread.start()
            self.threads.append(thread)
        
        print(f"Started {len(self.dispatchers)} dispatchers")
    
    def _dispatcher_worker(self, dispatcher: Dispatcher):
        """Рабочая функция диспетчера"""
        while self.is_running:
            try:
                dispatcher.set_status(DispatcherStatus.IDLE)
                
                # Берем заказ из очереди с таймаутом для проверки остановки
                try:
                    order = self.order_queue.get(timeout=0.5)
                    dispatcher.set_status(DispatcherStatus.PROCESSING)
                    self._process_order(dispatcher, order)
                    dispatcher.increment_processed()
                    
                except Empty:
                    continue
                    
            except Exception as e:
                print(f"Dispatcher {dispatcher.id} error: {e}")
                time.sleep(1)
    
    def _process_order(self, dispatcher: Dispatcher, order: Order):
        """Обрабатывает один заказ"""
        print(f"Dispatcher {dispatcher.id} processing order {order.uuid}")
        
        # Проверяем не отменен ли уже заказ
        if order.is_cancelled:
            print(f"Order {order.uuid} already cancelled, skipping")
            return
        
        # Ищем ближайшее такси
        taxi = self.taxi_service.find_nearest_taxi(order.from_location)
        
        if not taxi:
            print(f"No available taxi for order {order.uuid}. Requeuing.")
            # Возвращаем заказ в очередь для повторной обработки
            self.order_queue.put(order)
            return
        
        # Назначаем такси заказу
        with taxi.lock:
            taxi.status = TaxiStatus.BUSY
            taxi.order = order
            order.taxi = taxi
        
        print(f"Dispatcher {dispatcher.id} assigned Taxi {taxi.id} (speed: {taxi.speed}) to Order {order.uuid}")
        
        # Уведомляем клиента, что такси найдено
        order.assigned_event.set()
        
        # Запускаем симуляцию поездки в отдельном потоке
        ride_thread = threading.Thread(
            target=self.taxi_service.simulate_ride,
            args=(taxi, order),
            daemon=True,
            name=f"TaxiRide-{taxi.id}"
        )
        ride_thread.start()
    
    def stop(self):
        """Останавливает всех диспетчеров"""
        self.is_running = False
        for thread in self.threads:
            thread.join(timeout=1.0)
        print("Dispatchers stopped")


class ClientService:
    """Сервис для управления клиентами и их терпением"""
    
    def __init__(self, order_queue: Queue):
        self.order_queue = order_queue
        self.active_clients = {}
        self.is_running = False
        self.threads = []
    
    def create_client(self, from_location: Tuple[int, int], to_location: Tuple[int, int], 
                     patience: float = 30.0) -> Optional[Client]:
        """Создает клиента и его заказ"""
        client = Client(
            id=len(self.active_clients) + 1,
            location=from_location,
            patience_timeout=patience
        )
        
        order = client.place_order(to_location, self.order_queue)
        if order:
            self.active_clients[client.id] = client
            self._start_client_waiting(client)
            return client
        return None
    
    def _start_client_waiting(self, client: Client):
        """Запускает отсчет терпения клиента"""
        if client.current_order:
            thread = threading.Thread(
                target=self._client_waiting_worker,
                args=(client,),
                daemon=True,
                name=f"ClientWait-{client.id}"
            )
            thread.start()
            self.threads.append(thread)
    
    def _client_waiting_worker(self, client: Client):
        """Отслеживает терпение клиента"""
        if not client.current_order:
            return
            
        try:
            # Ждем назначения такси или истечения терпения
            assigned = client.current_order.assigned_event.wait(timeout=client.patience_timeout)
            
            if not assigned and not client.current_order.is_cancelled:
                # Таймаут истек - отменяем заказ
                client.current_order.cancel()
                print(f"Client {client.id} got impatient and cancelled order")
                
        except Exception as e:
            print(f"Client {client.id} waiting error: {e}")
    
    def stop(self):
        """Останавливает сервис клиентов"""
        self.is_running = False
        for thread in self.threads:
            thread.join(timeout=0.5)
        print("Client service stopped")