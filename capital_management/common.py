import pandas as pd


def prepare_data(stock_data_file_name: str):
    df = pd.read_csv(stock_data_file_name,
                     decimal=',',
                     parse_dates=['timestamp'],
                     date_parser=lambda x: pd.to_datetime(x, format='%y%m%d'))

    df['timestamp'] = df['timestamp'].dt.strftime("%Y-%m-%d")
    df.set_index('timestamp')

    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = df[col].astype(float).round(2)

    return df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
