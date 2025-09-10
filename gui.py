# gui.py

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, Tuple, List, Optional
import threading
import time
from PIL import Image, ImageTk
import math

from entities import ClientStatus, Taxi, TaxiStatus, Order, Client
from services import TaxiService, DispatcherService, ClientService


class TaxiParkGUI:
    """Графический интерфейс для симуляции таксопарка"""
    
    def __init__(self, root, simulator):
        self.root = root
        self.simulator = simulator
        
        # Инициализация словарей для иконок
        self.taxi_icons = {}  # Для хранения canvas ID такси
        self.client_icons = {}  # Для хранения canvas ID клиентов
        self.taxi_texts = {}  # Для хранения текстовых меток такси
        self.after_id = None
        
        self.setup_gui()
        
    def setup_gui(self):
        """Настройка интерфейса"""
        self.root.title("Таксопарк - Симуляция")
        self.root.geometry("1200x800")
        
        # Основной фрейм
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Canvas для карты
        self.canvas = tk.Canvas(main_frame, width=800, height=600, bg='lightblue')
        self.canvas.grid(row=0, column=0, rowspan=4, padx=5, pady=5)
        
        # Панель управления
        control_frame = ttk.Frame(main_frame)
        control_frame.grid(row=0, column=1, sticky=(tk.N, tk.W, tk.E), padx=5)
        
        # Кнопки управления
        ttk.Button(control_frame, text="Запуск", command=self.start_simulation).grid(row=0, column=0, pady=2)
        ttk.Button(control_frame, text="Стоп", command=self.stop_simulation).grid(row=0, column=1, pady=2)
        ttk.Button(control_frame, text="Тестовый заказ", command=self.create_test_order).grid(row=1, column=0, columnspan=2, pady=2)
        
        # Статистика
        stats_frame = ttk.LabelFrame(main_frame, text="Статистика", padding="5")
        stats_frame.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=5, pady=5)
        
        self.stats_vars = {
            'taxis_free': tk.StringVar(value="Свободных такси: 0"),
            'taxis_busy': tk.StringVar(value="Занятых такси: 0"),
            'orders_waiting': tk.StringVar(value="Заказов в очереди: 0"),
            'orders_processed': tk.StringVar(value="Обработано заказов: 0")
        }
        
        for i, (key, var) in enumerate(self.stats_vars.items()):
            ttk.Label(stats_frame, textvariable=var).grid(row=i, column=0, sticky=tk.W)
        
        # Лог событий
        log_frame = ttk.LabelFrame(main_frame, text="Лог событий", padding="5")
        log_frame.grid(row=2, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)
        
        self.log_text = tk.Text(log_frame, height=15, width=40)
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # Настройка весов для растягивания
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(2, weight=1)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        
    def start_simulation(self):
        """Запуск симуляции"""
        self.log("Запуск симуляции...")
        self.simulator.start_dispatchers()
        self.start_animation()
        
    def stop_simulation(self):
        """Остановка симуляции"""
        self.log("Остановка симуляции...")
        self.simulator.stop()
        if self.after_id:
            self.root.after_cancel(self.after_id)
            self.after_id = None
            
    def create_test_order(self):
        """Создание тестового заказа"""
        import random
        start_x, start_y = random.randint(50, 700), random.randint(50, 500)
        end_x, end_y = random.randint(50, 700), random.randint(50, 500)
        
        client = self.simulator.client_service.create_client(
            (start_x, start_y), 
            (end_x, end_y),
            patience=20.0
        )
        
        if client:
            self.log(f"Создан тестовый заказ от клиента {client.id}")
    
    def draw_client(self, client: Client):
        """Рисует клиента на карте"""
        if client.status == ClientStatus.REFUSED or client.status == ClientStatus.ON_RIDE:
            return
        x, y = client.location
        client_id = f"client_{client.id}"
        
        if client_id in self.client_icons:
            # Обновляем позицию
            self.canvas.coords(self.client_icons[client_id], x-4, y-4, x+4, y+4)
        else:
            # Создаем нового клиента
            icon = self.canvas.create_rectangle(x-4, y-4, x+4, y+4, fill="red", outline="black")
            self.client_icons[client_id] = icon
            # Добавляем текст с ID клиента
            text_id = self.canvas.create_text(x, y-10, text=f"C{client.id}", font=("Arial", 8))
            self.client_icons[f"{client_id}_text"] = text_id
    
    def draw_taxi(self, taxi: Taxi):
        """Рисует такси на карте"""
        x, y = taxi.get_location()
        taxi_id = f"taxi_{taxi.id}"
        
        if taxi_id in self.taxi_icons:
            # Обновляем позицию существующего такси
            self.canvas.coords(self.taxi_icons[taxi_id], x-6, y-6, x+6, y+6)
            # Обновляем цвет
            self.canvas.itemconfig(self.taxi_icons[taxi_id], fill=self.get_taxi_color(taxi.status))
            # Обновляем позицию текста
            self.canvas.coords(self.taxi_texts[f"{taxi_id}_id"], x, y-15)
            self.canvas.coords(self.taxi_texts[f"{taxi_id}_speed"], x, y+15)
        else:
            # Создаем новое такси
            icon = self.canvas.create_oval(x-6, y-6, x+6, y+6, 
                                         fill=self.get_taxi_color(taxi.status),
                                         outline="black")
            self.taxi_icons[taxi_id] = icon
            
            # Добавляем ID такси
            id_text = self.canvas.create_text(x, y-15, text=f"T{taxi.id}", font=("Arial", 8, "bold"))
            self.taxi_texts[f"{taxi_id}_id"] = id_text
            
            # Добавляем скорость
            speed_text = self.canvas.create_text(x, y+15, text=f"{taxi.speed:.1f}", font=("Arial", 7))
            self.taxi_texts[f"{taxi_id}_speed"] = speed_text
    
    def get_taxi_color(self, status: TaxiStatus) -> str:
        """Возвращает цвет для статуса такси"""
        colors = {
            TaxiStatus.FREE: "green",
            TaxiStatus.BUSY: "orange",
            TaxiStatus.MOVING_TO_CLIENT: "blue",
            TaxiStatus.ON_RIDE: "red",
            TaxiStatus.ON_WAY: "yellow"
        }
        return colors.get(status, "gray")
    
    def update_stats(self):
        """Обновление статистики"""
        free_taxis = sum(1 for taxi in self.simulator.taxis if taxi.status == TaxiStatus.FREE)
        busy_taxis = len(self.simulator.taxis) - free_taxis
        
        self.stats_vars['taxis_free'].set(f"Свободных такси: {free_taxis}")
        self.stats_vars['taxis_busy'].set(f"Занятых такси: {busy_taxis}")
        self.stats_vars['orders_waiting'].set(f"Заказов в очереди: {self.simulator.order_queue.qsize()}")
        
        processed = sum(d.processed_orders for d in self.simulator.dispatchers)
        self.stats_vars['orders_processed'].set(f"Обработано заказов: {processed}")
    
    def update_display(self):
        """Обновление отображения"""
        try:
            # Очищаем canvas
            self.canvas.delete("all")
            self.taxi_icons.clear()
            self.client_icons.clear()
            self.taxi_texts.clear()
            
            # Рисуем такси
            for taxi in self.simulator.taxis:
                self.draw_taxi(taxi)
            
            # Рисуем клиентов
            for client_id, client in self.simulator.client_service.active_clients.items():
                self.draw_client(client)
            
            # Обновляем статистику
            self.update_stats()
            
            # Запускаем следующий кадр анимации
            self.after_id = self.root.after(100, self.update_display)
            
        except Exception as e:
            self.log(f"Ошибка обновления дисплея: {e}")
            # Перезапускаем анимацию в случае ошибки
            self.after_id = self.root.after(1000, self.update_display)
    
    def start_animation(self):
        """Запуск анимации"""
        if not self.after_id:
            self.update_display()
    
    def log(self, message: str):
        """Добавление сообщения в лог"""
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        
    def run(self):
        """Запуск GUI"""
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()
        
    def on_closing(self):
        """Обработчик закрытия окна"""
        self.stop_simulation()
        self.root.destroy()