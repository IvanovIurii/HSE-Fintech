import csv

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from datetime import datetime
from ta.momentum import ROCIndicator


def parseData(file_name: str, start_date: str):
    historical_data = []

    with open(file_name, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            timestamp = row['datetime'].split(" ")[0]
            timestamp = datetime.strptime(timestamp, '%Y-%m-%d')  # skip time

            if timestamp > datetime.fromisoformat(start_date):
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

    data['action_timestamp'] = pd.NA
    data.loc[(data['action'] != pd.NA), 'action_timestamp'] = data['date'] + pd.Timedelta(days=2)

    return data


def show_charts(data, trades):
    buy_signals = data[data['action'] == 'buy']
    sell_signals = data[data['action'] == 'sell']

    my_buys = [trade['timestamp'] for trade in trades if trade['action'] == 'buy']
    my_sells = [trade['timestamp'] for trade in trades if trade['action'] == 'sell']
    my_buys = buy_signals[buy_signals['action_timestamp'].isin(my_buys)]
    my_sells = sell_signals[sell_signals['action_timestamp'].isin(my_sells)]

    # remove sell signals if they are before buy signals
    idx = 0
    while sell_signals.iloc[idx]['action_timestamp'] < buy_signals.iloc[0]['action_timestamp']:
        sell_signals = sell_signals.iloc[1:]
        idx += 1

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.15,
        subplot_titles=("Price chart with Buy/Sell Signals", "Rate of Change (ROC) Indicator"),
        row_heights=[0.7, 0.3]
    )

    fig.add_trace(go.Candlestick(
        x=data['action_timestamp'],
        open=data['open'],
        high=data['high'],
        low=data['low'],
        close=data['close'],
        name='Close Price'
    ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=buy_signals['action_timestamp'],
        y=buy_signals['low'] - 10,  # Place buy marker slightly below the low of the candle for better observability
        mode='markers',
        marker=dict(symbol='triangle-up', color='green', size=15),
        name='Buy Signal'
    ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=sell_signals['action_timestamp'],
        y=sell_signals['low'] - 10,  # Place buy marker slightly below the low of the candle
        mode='markers',
        marker=dict(symbol='triangle-up', color='red', size=15),
        name='Sell Signal'
    ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=my_buys['action_timestamp'],
        y=my_buys['low'] - 20,
        mode='markers',
        marker=dict(symbol='cross-open', color='green', size=10),
        name='Trade Opened'
    ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=my_sells['action_timestamp'],
        y=my_sells['low'] - 20,
        mode='markers',
        marker=dict(symbol='cross', color='black', size=10),
        name='Trade Closed'
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


def calculate_statistics(data):
    buy_prices = []
    sell_prices = []
    trades = []
    total_profit = 0

    is_open_position = False

    for index, row in data.iterrows():
        if row['action'] == 'buy':
            buy_price = row['close']
            buy_prices.append(buy_price)

            trades.append(
                {
                    'action': 'buy',
                    'timestamp': row['action_timestamp'],
                    'price': buy_price,
                    'status': 'OPEN'
                }
            )
            is_open_position = True
        elif row['action'] == 'sell' and is_open_position:
            sell_price = row['close']
            sell_prices.append(sell_price)

            profit = 0
            for trade in trades:
                if trade['status'] == 'OPEN':
                    profit += (sell_price - trade['price'])
                    trade['status'] = 'CLOSED'

            trades.append(
                {
                    'action': 'sell',
                    'timestamp': row['action_timestamp'],
                    'price': sell_price,
                    'profit': profit,
                    'status': 'CLOSED_ALL'
                }
            )
            total_profit += profit
            is_open_position = False

    win_trades = [trade for trade in trades if 'profit' in trade and trade['profit'] > 0]
    loss_trades = [trade for trade in trades if 'profit' in trade and trade['profit'] <= 0]
    total_trades = len([trade for trade in trades if 'profit' in trade])
    win_rate = (len(win_trades) / total_trades) * 100
    average_profit = total_profit / total_trades

    buy_orders = [trade for trade in trades if trade['action'] == 'buy']
    sell_orders = [trade for trade in trades if trade['action'] == 'sell']

    # todo: rearrange prints
    print(f"Buy orders: {len(buy_orders)}, Sell orders: {len(sell_orders)}")

    print(f"Total Profit: {total_profit:.2f}")
    print(f"Total Trades: {total_trades}")

    print(f"Win Rate: {win_rate:.2f}%")
    print(f"Average Profit per Trade: {average_profit:.2f}")
    print(f"Number of Wins: {len(win_trades)}, Number of Losses: {len(loss_trades)}")
    print(f"Win/Loss Rate: {len(win_trades) / len(loss_trades)}")

    return trades


def main(stock_data_file_name: str, roc_window: int, start_date: str, end_date: str):
    data = parseData(stock_data_file_name, start_date)
    data = get_roc_indicator(data, roc_window)
    data = data.loc[start_date:end_date]
    data = prepare_buy_sell_signals(data)
    data = prepare_buy_sell_actions(data)

    trades = calculate_statistics(data)
    show_charts(data, trades)


# todo: add parameter to smooth ROC by MA
# so test just with 2 parameters
main(
    './resources/AAPL.csv',
    14,
    start_date='2014-01-01',
    end_date='2024-12-31'
)
