import csv

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from datetime import datetime
from ta.momentum import ROCIndicator


def parseData(file_name: str):
    historical_data = []

    with open(file_name, 'r') as f:
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
    data['date'] = data.index

    return data


def get_roc_indicator(data, roc_window: int):
    data['roc'] = ROCIndicator(data['close'], window=roc_window).roc()

    return data


def prepare_buy_sell_signals(data):
    data['signal'] = 0
    data['signal'][data['roc'] > 0] = 1
    data['signal'][data['roc'] < 0] = -1

    return data


def prepare_buy_sell_actions(data):
    data['group'] = (data['signal'] != data['signal'].shift(1)).cumsum()

    grouped_data = data.groupby(['group', 'signal']).agg(
        timestamp=('date', 'first'),
        count=('signal', 'size')
    ).reset_index()

    # On signal wait:
    # buy when 2 bars after the signal;
    # sell after 2 bars after the signal.
    grouped_data['action'] = pd.NA
    grouped_data.loc[(grouped_data['count'] > 2) & (grouped_data['signal'] == 1), 'action'] = 'buy'
    grouped_data.loc[(grouped_data['count'] > 2) & (grouped_data['signal'] == -1), 'action'] = 'sell'

    grouped_data_to_merge = pd.DataFrame(grouped_data.to_dict(orient='records'))

    data = pd.merge(
        data,
        grouped_data_to_merge[['timestamp', 'action']],
        on='timestamp',
        how='left'
    )
    data['action'] = data['action'].fillna(-1)

    return data


def show_charts(data):
    buy_signals = data[data['action'] == 'buy']
    sell_signals = data[data['action'] == 'sell']

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.15,
        subplot_titles=("Price chart with Buy/Sell Signals", "Rate of Change (ROC) Indicator"),
        row_heights=[0.7, 0.3]
    )

    fig.add_trace(go.Candlestick(
        x=data['date'],
        open=data['open'],
        high=data['high'],
        low=data['low'],
        close=data['close'],
        name='Close Price'
    ), row=1, col=1)

    # todo: extract to single method traces below
    fig.add_trace(go.Scatter(
        x=buy_signals['date'],
        y=buy_signals['low'] - 10,  # Place buy marker slightly below the low of the candle for better observability
        mode='markers',
        marker=dict(symbol='triangle-up', color='green', size=15),
        name='Buy Signal'
    ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=sell_signals['date'],
        y=sell_signals['low'] - 10,  # Place buy marker slightly below the low of the candle
        mode='markers',
        marker=dict(symbol='triangle-up', color='red', size=15),
        name='Sell Signal'
    ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=data['date'],
        y=data['roc'],
        mode='lines',
        name='ROC',
        line=dict(color='black', width=2)
    ), row=2, col=1)

    fig.update_layout(
        title="Stock chart - ROC based strategy with signals",
        xaxis_title="Date",
        yaxis_title="Price",
        xaxis_rangeslider_visible=False,
        height=800,
        showlegend=True
    )

    fig.update_yaxes(title_text="Price", row=1, col=1)
    fig.update_yaxes(title_text="ROC (%)", row=2, col=1)

    fig.show()


def main(stock_data_file_name: str, roc_window: int, start_date: str, end_date: str):
    data = parseData(stock_data_file_name)

    data = get_roc_indicator(data, roc_window)
    data = data.loc[start_date:end_date]
    data = prepare_buy_sell_signals(data)
    data = prepare_buy_sell_actions(data)

    show_charts(data)


main('./resources/AAPL.csv', 14, start_date='2022-01-01', end_date='2024-12-31')

# todo: move to its own method calculate profit
# buy_prices = []
# sell_prices = []

# how much to buy?
# how many assets at close price?

# for index, row in data.iterrows():
#     if row['action'] == 'buy':
#         buy_price = row['close']
#         buy_prices.append(buy_price)
#     elif row['action'] == 'sell':
#         sell_price = row['close']
#         sell_prices.append(sell_price)
#
# result = sum(buy_prices) - sum(sell_prices)


# TODO: calculate returns
# TODO: when to start and how much to invest?
