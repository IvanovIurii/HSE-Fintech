import numpy as np
import pandas as pd

from capital_management.common import prepare_data
from ta.trend import sma_indicator
import plotly.graph_objects as go
import matplotlib.pyplot as plt


def visualize(data):
    fig = go.Figure()

    # plot closing price
    fig.add_trace(
        go.Scatter(x=data.index,
                   y=data['close'],
                   mode='lines',
                   name='Close Price',
                   line=dict(color='blue', width=2)))

    # plot SMAs
    fig.add_trace(
        go.Scatter(x=data.index,
                   y=data['SMA20'],
                   mode='lines',
                   name='SMA 20',
                   line=dict(color='orange', width=2)))

    fig.add_trace(
        go.Scatter(x=data.index,
                   y=data['SMA40'],
                   mode='lines',
                   name='SMA 40',
                   line=dict(color='green', width=2)))

    fig.update_layout(
        title='Price with SMA Crossover',
        xaxis_title='Date',
        yaxis_title='Price',
        height=800,
        showlegend=True
    )

    fig.show()


def main():
    # load historical data
    data = prepare_data("../resources/GMKN.csv")

    # compute two simple moving averages (SMA20 and SMA40)
    data['SMA20'] = sma_indicator(data['close'], window=20)
    data['SMA40'] = sma_indicator(data['close'], window=40)

    # generate signals based on the SMA crossovers;
    # when the 20‑day SMA crosses above the 40‑day SMA = LONG;
    # when it crosses below = SHORT
    data['Signal'] = 0
    data.loc[(data['SMA20'] > data['SMA40']), 'Signal'] = 1
    data.loc[(data['SMA20'] < data['SMA40']), 'Signal'] = -1

    # remove NA after lag
    data = data.dropna()

    # visualize current situation if needed
    # visualize(data)

    # simulation with Anti-Martingale Capital Management
    # initial capital, RUB
    initial_capital = 1_000_000
    # current
    capital = initial_capital

    # use 1% as an initial trade size, 10k RUB
    base_trade_size = 0.01 * initial_capital

    # this will be doubled if there was a win trade, and reset if it was a loss
    position_multiplier = 1

    # each trade profit
    trade_profits = []
    # equity curve is a representation of the change in the value of a trading account over time (after each trade)
    equity_curve = [capital]
    # to store details of every trade
    trade_details = []

    # to track current open position and statistics
    in_position = False
    entry_price = None
    # long (1) or short(-1)
    entry_signal = None
    trade_entry_date = None

    # loop over each day
    for _, row in data.iterrows():
        signal = row['Signal']
        price = row['close']

        if not in_position:
            in_position = True
            entry_signal = signal
            entry_price = price
            trade_entry_date = row['timestamp']
        else:
            # if already in a position, check if the signal reverses the trade
            if signal != entry_signal:
                # close the current trade at the current price
                exit_price = price
                trade_exit_date = row['timestamp']

                # calculate trade return, %
                if entry_signal == 1:
                    # for long
                    trade_return = (exit_price - entry_price) / entry_price
                else:
                    # for short
                    trade_return = (entry_price - exit_price) / entry_price

                # Determine the trade size using the anti-martingale multiplier.
                trade_size = base_trade_size * position_multiplier

                # calculate profit for this trade, RUB
                profit = trade_size * trade_return

                # update capital
                capital += profit

                # record the trade result
                trade_profits.append(profit)
                trade_details.append({
                    'Entry Date': trade_entry_date,
                    'Exit Date': trade_exit_date,
                    'Entry Price': entry_price,
                    'Exit Price': exit_price,
                    'Signal': entry_signal,
                    'Return': trade_return,  # %
                    'Profit': profit,  # RUB
                    'Trade Size': trade_size,
                    'Capital After Trade': capital
                })
                equity_curve.append(capital)

                # Anti-Martingale:
                # if the trade was profitable, double the multiplier;
                # if not, reset the multiplier back to 1
                if profit > 0:
                    position_multiplier *= 2
                else:
                    position_multiplier = 1

                # open a new trade with based on the signal (long or short)
                in_position = True
                entry_signal = signal
                entry_price = price
                trade_entry_date = row['timestamp']

    # if a trade is still open at the end of the period, close it at the last available price
    if in_position:
        exit_price = data.iloc[-1]['close']
        trade_exit_date = data.index[-1]

        if entry_signal == 1:
            trade_return = (exit_price - entry_price) / entry_price
        else:
            trade_return = (entry_price - exit_price) / entry_price

        trade_size = base_trade_size * position_multiplier
        profit = trade_size * trade_return
        capital += profit
        trade_profits.append(profit)
        trade_details.append({
            'Entry Date': trade_entry_date,
            'Exit Date': trade_exit_date,
            'Entry Price': entry_price,
            'Exit Price': exit_price,
            'Signal': entry_signal,
            'Return': trade_return,
            'Profit': profit,
            'Trade Size': trade_size,
            'Capital After Trade': capital
        })
        equity_curve.append(capital)

    # Performance Metrics
    total_profit = capital - initial_capital
    # standard deviation
    std_profit = np.std(trade_profits)
    # Drawdown: the largest drop (in %) from a peak in the equity curve
    equity_array = np.array(equity_curve)
    max = np.maximum.accumulate(equity_array)
    drawdowns = (max - equity_array) / max
    max_drawdown = np.max(drawdowns) * 100  # %

    # Sharpe Ratio:
    sharpe_ratio = np.mean(trade_profits) / std_profit

    print("=== Trading Performance Indicators ===")
    print("Total Profit: {:.2f} rubles".format(total_profit))
    print("Standard Deviation of Profit: {:.2f}".format(std_profit))
    print("Maximum Drawdown: {:.2f}%".format(max_drawdown))
    print("Sharpe Ratio: {:.2f}".format(sharpe_ratio))

    trades_df = pd.DataFrame(trade_details)
    print("\nTrade Details:")
    print(trades_df)

    # plot the equity curve
    plt.figure(figsize=(10, 6))
    plt.plot(equity_curve, label='Equity Curve')
    plt.title("Equity Curve Over Time")
    plt.xlabel("Number of Trade")
    plt.ylabel("Capital (RUB)")
    plt.legend()
    plt.grid(True)
    plt.show()


if __name__ == '__main__':
    main()
