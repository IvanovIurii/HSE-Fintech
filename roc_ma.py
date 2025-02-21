import csv

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from datetime import datetime
from ta.momentum import ROCIndicator
from ta.trend import sma_indicator


def parseData(file_name: str, start_date: str):
    """Parse CSV data and filter by start_date."""
    historical_data = []

    with open(file_name, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            timestamp = row['datetime'].split(" ")[0]
            timestamp = datetime.strptime(timestamp, '%Y-%m-%d')  # skip time

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


def get_smoothed_roc_indicator(data, roc_window: int, sma_window: int):
    """Add the Rate-of-Change (ROC) indicator column."""
    data['roc'] = ROCIndicator(data['close'], window=roc_window).roc()
    data['roc'] = sma_indicator(data['roc'], window=sma_window)

    return data


def prepare_buy_sell_signals(data):
    """Assign a trading signal based on the sign of the ROC value."""
    data['signal'] = 0
    data['signal'][data['roc'] > 0] = 1
    data['signal'][data['roc'] < 0] = -1

    return data


def prepare_buy_sell_actions(data, exit):
    """
    Group consecutive signals and assign an action when the group lasts for more than 2 bars.
    The trade is executed 2 days after the signal.
    The sell happens after exit amount of bars.
    """
    data['group'] = (data['signal'] != data['signal'].shift(1)).cumsum()

    grouped_data = data.groupby(['group', 'signal']).agg(
        timestamp=('date', 'first'),
        count=('signal', 'size')
    ).reset_index()

    grouped_data['action'] = pd.NA
    grouped_data.loc[(grouped_data['count'] > 2) & (grouped_data['signal'] == 1), 'action'] = 'buy'
    grouped_data.loc[(grouped_data['count'] > exit) & (grouped_data['signal'] == -1), 'action'] = 'sell'

    grouped_data_to_merge = pd.DataFrame(grouped_data.to_dict(orient='records'))

    data = pd.merge(
        data,
        grouped_data_to_merge[['timestamp', 'action']],
        on='timestamp',
        how='left'
    )
    data['action'] = data['action'].fillna(-1)

    data['action_timestamp'] = pd.NA
    data.loc[(data['action'] != pd.NA), 'action_timestamp'] = data['date'].shift(-exit)

    return data


# (Optional) Chart function remains available if you wish to visualize any specific run
def show_charts(data):
    buy_signals = data[data['action'] == 'buy']
    sell_signals = data[data['action'] == 'sell']

    # remove sell signals if they are before buy signals
    while sell_signals.iloc[0]['action_timestamp'] < buy_signals.iloc[0]['action_timestamp']:
        sell_signals = sell_signals.iloc[1:]

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
                    trade_profit = (sell_price - trade['price'])
                    profit += trade_profit
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

    buy_orders = [trade for trade in trades if trade['action'] == 'buy']
    sell_orders = [trade for trade in trades if trade['action'] == 'sell']

    win_trades = [trade for trade in trades if 'profit' in trade and trade['profit'] > 0]
    loss_trades = [trade for trade in trades if 'profit' in trade and trade['profit'] <= 0]

    total_trades = len(buy_orders + sell_orders)

    win_rate = (len(win_trades) / len(win_trades + loss_trades)) * 100
    average_profit = total_profit / len([trade for trade in trades if 'profit' in trade])

    win_loss_ration = len(win_trades) / len(loss_trades) if loss_trades else 0

    # todo: use this to round all the floats inside the DF
    # df_rounded = df.round(2)
    stats = {
        'total_profit': total_profit,
        'total_trades': total_trades,
        'win_rate': win_rate,
        'win_loss_ratio': format(win_loss_ration, ".2f"),
        'average_profit': average_profit,
        'wins': len(win_trades),
        'losses': len(loss_trades),
        'buy_orders': len(buy_orders),
        'sell_orders': len(sell_orders),
    }

    return stats


def print_stats(stats: dict):
    print(f"Total Trades: {stats['total_trades']}")
    print(f"Total Profit: {stats['total_profit']:.2f}")
    print(f"Average Profit per Trade: {stats['average_profit']:.2f}")
    print(f"Win Rate: {stats['win_rate']:.2f}%")
    print(f"Number of Wins: {stats['wins']}, Number of Losses: {stats['losses']}")

    if stats['win_loss_ratio'] != '0.00':
        print(f"Win/Loss Ratio: {stats['win_loss_ratio']}")
    else:
        print("No Loss Trades.")


def backtest_single_run(stock_data_file_name: str, roc_window: int, sma_window: int, exit: int, start_date: str,
                        end_date: str):
    data = parseData(stock_data_file_name, start_date)
    data = get_smoothed_roc_indicator(data, roc_window, sma_window)
    data = data.loc[start_date:end_date]
    data = prepare_buy_sell_signals(data)
    data = prepare_buy_sell_actions(data, exit)

    stats = calculate_statistics(data)
    print_stats(stats)

    show_charts(data)


def backtest(stock_data_file_name: str, start_date: str, end_date: str):
    results = []
    for roc_window in range(10, 31):  # ROC Window
        for sma_window in [100, 250]:  # SMA Window
            for exit in [5, 10, 15, 20]:  # Exit
                data = parseData(stock_data_file_name, start_date)
                data = get_smoothed_roc_indicator(data, roc_window, sma_window)
                data = data.loc[start_date:end_date]
                data = prepare_buy_sell_signals(data)
                data = prepare_buy_sell_actions(data, exit)

                stats = calculate_statistics(data)
                stats['roc_window'] = roc_window
                stats['sma_window'] = sma_window
                stats['exit'] = exit

                if stats['total_trades'] >= 30:
                    results.append(stats)

    if not results:
        print("No results with more than 30 trades")
        return

    table = pd.DataFrame(results)
    print("\n=== Backtest Summary for All ROC Windows ===")

    print(table[[
        'roc_window',
        'exit',
        'sma_window',
        'buy_orders',
        'total_trades',
        'wins',
        'losses',
        'average_profit',
        'total_profit',
        'win_loss_ratio']])

    print(table.head())
    print("Number of rows:", len(table))
    max_row = table.loc[table['win_loss_ratio'].idxmax()]

    # now with this values we can run a single strategy to see the chart
    print("\nMax Win Loss Ratio:")
    print(max_row)

    return table


if __name__ == "__main__":
    # Define parameters (adjust these paths and dates as needed)
    stock_data_file_name = './resources/LKOH.csv'
    start_date = '2018-01-01'
    end_date = '2024-08-31'

    # TO BACKTEST TO FIND PARAMETERS
    # start_date = '2000-01-01'
    # end_date = '2018-01-01'

    # TO CHECK ON PAPER
    # start_date = '2018-01-01'
    # end_date = '2024-08-31'

    # result = backtest(stock_data_file_name, start_date, end_date)

    # Optional:
    # if you need to check single result with defined parameters and chars
    # to visualize this specific run, for example roc_window=14:
    backtest_single_run(
        stock_data_file_name=stock_data_file_name,
        roc_window=21,
        sma_window=100,
        exit=10,
        start_date=start_date,
        end_date=end_date
    )
