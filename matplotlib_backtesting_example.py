import ta
import csv
import pandas as pd
from datetime import datetime
import plotly.graph_objects as go

historical_data = []

with open('./resources/AAPL.csv', 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        timestamp = row['datetime'].split(" ")[0]
        timestamp = datetime.strptime(timestamp, '%Y-%m-%d')  # skip time

        if timestamp > datetime.fromisoformat('1999-01-01'):
            historical_data.append({
                'timestamp': timestamp,
                'open': float(row['open']),
                'high': float(row['high']),
                'low': float(row['low']),
                'close': float(row['close']),
                'volume': float(row['volume'])
            })

data = pd.DataFrame(historical_data)
data.set_index('timestamp', inplace=True)

data['RSI'] = ta.momentum.RSIIndicator(data['close'], window=14).rsi()

# narrow the time period
data = data.loc['2022-01-01':'2025-01-31']

data['SMA_50'] = ta.trend.sma_indicator(data['close'], window=50)
data['SMA_200'] = ta.trend.sma_indicator(data['close'], window=200)

data['Buy_Signal'] = (data['RSI'] < 30) & (data['SMA_50'] > data['SMA_200'])  # Oversold and SMA crossover
data['Sell_Signal'] = (data['RSI'] > 70) & (data['SMA_50'] < data['SMA_200'])  # Overbought and SMA crossover

fig = go.Figure()

# Plot closing price
fig.add_trace(
    go.Scatter(x=data.index, y=data['close'], mode='lines', name='Close Price', line=dict(color='blue', width=2)))

# Plot SMAs
fig.add_trace(
    go.Scatter(x=data.index, y=data['SMA_50'], mode='lines', name='SMA 50', line=dict(color='orange', width=2)))
fig.add_trace(
    go.Scatter(x=data.index, y=data['SMA_200'], mode='lines', name='SMA 200', line=dict(color='green', width=2)))

# Plot Buy Signals (green triangles)
fig.add_trace(go.Scatter(x=data.index[data['Buy_Signal']],
                         y=data['close'][data['Buy_Signal']],
                         mode='markers',
                         name='Buy',
                         marker=dict(symbol='triangle-up', color='green', size=10)))

# Plot Sell Signals (red triangles)
fig.add_trace(go.Scatter(x=data.index[data['Sell_Signal']],
                         y=data['close'][data['Sell_Signal']],
                         mode='markers',
                         name='Sell',
                         marker=dict(symbol='triangle-down', color='red', size=10)))

# Plot RSI chart
fig.add_trace(go.Scatter(x=data.index, y=data['RSI'], mode='lines', name='RSI', line=dict(color='purple', width=2)))

# Add overbought (70) and oversold (30) horizontal lines to the RSI chart
fig.add_trace(go.Scatter(x=data.index, y=[70] * len(data), mode='lines', name='Overbought (70)',
                         line=dict(color='red', dash='dash')))
fig.add_trace(go.Scatter(x=data.index, y=[30] * len(data), mode='lines', name='Oversold (30)',
                         line=dict(color='green', dash='dash')))

fig.update_layout(
    title='Price, SMA Crossover, and RSI combined',
    xaxis_title='Date',
    yaxis_title='Price',
    height=800,
    showlegend=True
)

fig.show()
