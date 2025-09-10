# main.py

import time
from queue import Queue
from typing import List, Tuple, Optional
import threading
import random

from entities import Taxi, Dispatcher, Client
from services import TaxiService, DispatcherService, ClientService, TaxiStatus
from gui import TaxiParkGUI
import tkinter as tk


class TaxiParkSimulator:
    """Фасад, управляющий всем симулятором."""
    
    def __init__(self, num_dispatchers, num_taxis):
        self.order_queue = Queue()
        self.taxis = self._create_taxis(num_taxis)
        self.dispatchers = self._create_dispatchers(num_dispatchers)
        
        # Инициализация сервисов
        self.taxi_service = TaxiService(self.taxis)
        self.dispatcher_service = DispatcherService(
            self.dispatchers, self.order_queue, self.taxi_service
        )
        self.client_service = ClientService(self.order_queue)
        
        self.is_running = False
        
    def _create_taxis(self, count: int) -> List[Taxi]:
        """Создает пул такси со случайным расположением"""
        return [
            Taxi(
                id=i, 
                color="yellow", 
                speed=random.uniform(3, 6),  # Разные скорости
                location=(random.randint(50, 750), random.randint(50, 550)),
                status=TaxiStatus.FREE
            ) 
            for i in range(count)
        ]
    
    def _create_dispatchers(self, count: int) -> List[Dispatcher]:
        """Создает диспетчеров"""
        return [Dispatcher(id=i) for i in range(count)]
    
    def start_dispatchers(self):
        """Запускает всех диспетчеров"""
        self.is_running = True
        self.dispatcher_service.start()
        print("Все сервисы запущены")
    
    def stop(self):
        """Останавливает симуляцию"""
        self.is_running = False
        self.dispatcher_service.stop()
        self.taxi_service.stop()
        self.client_service.stop()
        print("Все сервисы остановлены")
    
    def add_order(self, from_location: Tuple[int, int], to_location: Tuple[int, int]) -> Optional[Client]:
        """Публичный метод для создания заказа"""
        return self.client_service.create_client(from_location, to_location)


def main():
    """Основная функция запуска"""
    # Создаем симулятор
    simulator = TaxiParkSimulator(num_dispatchers=2, num_taxis=3)
    
    # Создаем GUI
    root = tk.Tk()
    app = TaxiParkGUI(root, simulator)
    
    # Добавляем несколько тестовых заказов
    def add_initial_orders():
        time.sleep(1)  # Даем GUI время для инициализации
        for i in range(3):
            start_x, start_y = random.randint(100, 700), random.randint(100, 500)
            end_x, end_y = random.randint(100, 700), random.randint(100, 500)
            simulator.add_order((start_x, start_y), (end_x, end_y))
            time.sleep(0.5)
    
    # Запускаем добавление заказов в отдельном потоке
    init_thread = threading.Thread(target=add_initial_orders, daemon=True)
    init_thread.start()
    
    # Запускаем GUI
    app.run()


if __name__ == "__main__":
    main()