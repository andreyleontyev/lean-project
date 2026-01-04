from AlgorithmImports import *
from datetime import datetime


class BinanceFundingRateData(PythonData):
    """
    Класс для чтения данных funding rate из CSV файла Binance.
    Формат файла: YYYYMMDD HHMMSS,funding_rate
    """
    
    def GetSource(self, config, date, isLiveMode):
        """
        Возвращает источник данных - путь к CSV файлу.
        
        Args:
            config: SubscriptionDataConfig
            date: DateTime - дата для которой нужны данные
            isLiveMode: bool - режим live торговли
            
        Returns:
            SubscriptionDataSource - источник данных
        """
        # Путь к файлу с данными
        file_path = "data/custom/lean_funding_rates/binance_funding_rate_BTC.csv"
        
        return SubscriptionDataSource(
            file_path,
            SubscriptionTransportMedium.LOCAL_FILE,
            FileFormat.CSV
        )
    
    def Reader(self, config, line, date, isLiveMode):
        """
        Парсит строку из CSV файла и возвращает объект данных.
        
        Args:
            config: SubscriptionDataConfig
            line: str - строка из CSV файла
            date: DateTime - дата для которой нужны данные
            isLiveMode: bool - режим live торговли
            
        Returns:
            BinanceFundingRateData или None если строка невалидна
        """
        # Пропускаем пустые строки
        if not line or line.strip() == "":
            return None
        
        try:
            # Разделяем строку по запятой
            parts = line.strip().split(',')
            if len(parts) != 2:
                return None
            
            # Парсим дату и время: "YYYYMMDD HHMMSS"
            date_str = parts[0].strip()
            if len(date_str) != 15:  # "YYYYMMDD HHMMSS" = 15 символов
                return None
            
            # Извлекаем дату и время
            year = int(date_str[0:4])
            month = int(date_str[4:6])
            day = int(date_str[6:8])
            hour = int(date_str[9:11])
            minute = int(date_str[11:13])
            second = int(date_str[13:15])
            
            # Создаем объект DateTime
            time = datetime(year, month, day, hour, minute, second)
            
            # Парсим funding rate
            funding_rate = float(parts[1].strip())
            
            # Создаем объект данных
            data = BinanceFundingRateData()
            data.Symbol = config.Symbol
            data.Time = time
            data.Value = funding_rate
            data.EndTime = time  # Время окончания периода (можно настроить по необходимости)
            
            return data
            
        except (ValueError, IndexError) as e:
            # Если не удалось распарсить строку, возвращаем None
            return None

