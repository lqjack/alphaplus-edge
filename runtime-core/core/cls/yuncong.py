"""
美股及A股模式化选股策略实现
包含数据获取、基本面筛选、技术分析、信号生成、回测及可视化功能
"""
import pandas as pd
import numpy as np
import talib
import yfinance as yf
from backtrader import Cerebro, feeds, strategies
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import logging

logger = logging.getLogger(__name__)  

# 配置参数
class Config:
    # 基本面参数
    MIN_ROE = 15       # 最小ROE(%)
    MAX_DEBT = 60      # 最大负债率(%)
    MIN_GROWTH = 20    # 最小营收增长率(%)
    
    # 技术面参数
    BREAKOUT_DAYS = 5  # 突破确认周期
    STOP_LOSS = 0.03   # 止损比例
    TAKE_PROFIT = 0.05 # 止盈比例
    
    # 回测参数
    START_DATE = '2020-01-01'
    END_DATE = '2023-08-01'
    INIT_CASH = 1000000

class StockSelector:
    """选股核心类"""
    
    def __init__(self):
        self.data_loader = DataLoader()
        self.technical = TechnicalAnalysis()
        
    def fundamental_screening(self, market='A'):
        """基本面筛选"""
        df = self.data_loader.load_fundamental_data(market)
        screened = df[
            (df['ROE'] >= Config.MIN_ROE) &
            (df['DebtRatio'] <= Config.MAX_DEBT) &
            (df['RevenueGrowth'] >= Config.MIN_GROWTH)
        ]
        return screened.index.tolist()
    
    def technical_screening(self, symbols):
        """技术面筛选"""
        signals = []
        for symbol in symbols:
            df = self.data_loader.load_price_data(symbol)
            if df.empty:
                continue
            
            # 计算技术指标
            df['MA20'] = talib.MA(df['Close'], timeperiod=20)
            df['RSI'] = talib.RSI(df['Close'])
            df['MACD'], _, _ = talib.MACD(df['Close'])
            
            # 突破信号检测
            df['Breakout'] = df['Close'] > df['High'].rolling(Config.BREAKOUT_DAYS).max().shift(1)
            
            # 最近交易日信号
            if df.iloc[-1]['Breakout'] and df.iloc[-1]['Volume'] > 1.5 * df['Volume'].mean():
                signals.append(symbol)
                
        return signals
    
    def get_selected_stocks(self, market='A'):
        """综合选股"""
        fundamental = self.fundamental_screening(market)
        technical = self.technical_screening(fundamental)
        return technical

class DataLoader:
    """数据加载类（示例实现）"""
    
    def load_fundamental_data(self, market):
        """加载基本面数据（示例数据）"""
        # 实际应接入数据库或API
        data = {
            'ROE': [18, 22, 12, 25],
            'DebtRatio': [55, 45, 70, 30],
            'RevenueGrowth': [25, 18, 30, 22]
        }
        return pd.DataFrame(data, index=['600519.SS', '000001.SS', 'AAPL', 'MSFT'])
    
    def load_price_data(self, symbol):
        """加载价格数据"""
        try:
            df = yf.download(symbol, start=Config.START_DATE, end=Config.END_DATE)
            return df
        except:
            return pd.DataFrame()

class TechnicalAnalysis:
    """技术分析工具类"""
    
    @staticmethod
    def detect_gap(df):
        """缺口检测"""
        df['GapUp'] = df['Low'] > df['High'].shift(1)
        df['GapDown'] = df['High'] < df['Low'].shift(1)
        return df
    
    @staticmethod
    def volume_analysis(df):
        """量价分析"""
        df['VolumeMA5'] = df['Volume'].rolling(5).mean()
        df['VolumeSpike'] = df['Volume'] > 2 * df['VolumeMA5']
        return df

class BacktestEngine:
    """回测引擎"""
    
    def __init__(self):
        self.cerebro = Cerebro()
        self.cerebro.broker.setcash(Config.INIT_CASH)
    
    def add_strategy(self):
        """添加双突破策略"""
        self.cerebro.addstrategy(BreakoutStrategy)
    
    def run_backtest(self, data):
        """运行回测"""
        data_feed = feeds.PandasData(dataname=data)
        self.cerebro.adddata(data_feed)
        return self.cerebro.run()
    
class BreakoutStrategy(strategies.Strategy):
    """双突破交易策略"""
    
    def __init__(self):
        self.order = None
        self.high_20 = talib.MAX(self.data.high, timeperiod=20)
        self.low_20 = talib.MIN(self.data.low, timeperiod=20)
        
    def next(self):
        if self.order:
            return  # 有未完成订单
        
        # 突破上轨买入
        if self.data.close[0] > self.high_20[0]:
            size = self.broker.getcash() // self.data.close[0]
            self.order = self.buy(size=size)
            
        # 突破下轨卖出
        elif self.data.close[0] < self.low_20[0] and self.position:
            self.order = self.sell(size=self.position.size)

# 主程序
if __name__ == "__main__":
    selector = StockSelector()
    
    # A股选股示例
    logger.info("正在进行A股选股...")
    selected_a = selector.get_selected_stocks(market='A')
    logger.info(f"选中股票: {selected_a}")
    
    # 回测示例
    engine = BacktestEngine()
    engine.add_strategy()
    data = yf.download('600519.SS', start=Config.START_DATE, end=Config.END_DATE)
    results = engine.run_backtest(data)
    
    # 可视化
    plt.style.use('seaborn')
    engine.cerebro.plot(style='candlestick')