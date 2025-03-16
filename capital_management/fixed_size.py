from capital_management.common import prepare_data
from ta.momentum import ROCIndicator
import matplotlib.pyplot as plt


def main():
    data = prepare_data("../resources/GMKN.csv")
    # roc window is 10, there is no a reason behind it
    data['roc'] = ROCIndicator(data['close'], window=10).roc()

    data['signal'] = 0
    data['signal'][data['roc'] > 0] = 1  # buy
    data['signal'][data['roc'] < 0] = -1  # sell

    data = data.dropna()

    initial_capital = 1_000_000

    trade_sizes_ranges = [
        range(10, 100, 10),
        range(100, 1000, 100),
        range(1000, 2000, 1000),
    ]

    profits = []
    ratios = []

    for trade_size_range in trade_sizes_ranges:
        # trade size in %
        for trade_size in trade_size_range:
            capital = initial_capital
            trade_capital = trade_size * capital / 100

            profit = 0
            in_position = False
            entry_price = None

            for _, row in data.iterrows():
                signal = row['signal']
                price = row['close']

                if not in_position:
                    # buy
                    if signal == 1:
                        entry_price = price
                        in_position = True
                # sell
                else:
                    # sell only if in position and there is roc sell signal coming
                    if signal == -1:
                        trade_return = (price - entry_price) / entry_price
                        profit = profit + trade_capital * trade_return
                        capital += profit
                        trade_capital = trade_size * capital / 100
                        # we sold everything
                        in_position = False

            if in_position:
                # sell everything with the latest close price
                trade_return = (data.iloc[-1]['close'] - entry_price) / entry_price
                profit = profit + trade_capital * trade_return

            # a big loss
            if profit < 0 and abs(profit) > initial_capital:
                print("Significant loss")
            else:
                profits.append(profit / initial_capital)
                ratios.append(trade_size)

    plt.figure(figsize=(10, 6))
    plt.plot(ratios, profits)
    plt.title("Зависимость итоговой прибыли от доли задействованного капитала")
    plt.xlabel("Доля капитала, %")
    plt.ylabel("Прибыль/Убыток, от начального капитала")

    plt.yscale('log')
    plt.grid(True, axis='y')
    plt.show()


if __name__ == "__main__":
    main()
