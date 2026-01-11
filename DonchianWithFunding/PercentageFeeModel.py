from AlgorithmImports import *

class PercentageFeeModel(FeeModel):

    def __init__(self, percent):
        self.percent = percent


    def GetOrderFee(self, parameters):
        # Считаем объем сделки: Цена * Количество
        val = parameters.Security.Price * abs(parameters.Order.Quantity) * self.percent
        # Возвращаем размер комиссии в валюте котировки (обычно USD)
        return OrderFee(CashAmount(val, parameters.Security.QuoteCurrency.Symbol))