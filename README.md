# Lean Trading Strategy Project

A QuantConnect Lean-based algorithmic trading project featuring a Bitcoin trading strategy with EMA crossover signals and risk management.

## Overview

This project implements an offline trading strategy using QuantConnect Lean Engine. The main strategy (`RealisticBitcoinStrategy`) trades Bitcoin using hourly data with exponential moving average (EMA) crossovers, stop-loss, and trailing stop mechanisms.

## Strategy Details

### RealisticBitcoinStrategy

- **Asset**: Bitcoin (BTC)
- **Timeframe**: Hourly (1h)
- **Indicators**: 
  - Fast EMA: 9 periods
  - Slow EMA: 21 periods
- **Entry Signal**: Fast EMA crosses above Slow EMA
- **Exit Signals**:
  - Fast EMA crosses below Slow EMA
  - Stop Loss: 3% below entry price
  - Trailing Stop: 5% below highest price since entry
- **Position Size**: 95% of portfolio
- **Commission**: 0.1% per trade
- **Backtest Period**: 2025-01-01 to 2026-01-01
- **Initial Capital**: $100,000

## Project Structure

```
lean-project/
├── MyOfflineStrategy/
│   ├── main.py              # Main strategy implementation
│   ├── config.json          # Strategy configuration
│   ├── research.ipynb       # Research notebook
│   └── backtests/           # Backtest results
├── Data/
│   ├── custom/              # Custom data files
│   │   ├── btc_1h.csv      # Bitcoin hourly data
│   │   └── spy.csv         # SPY data
│   └── [various data directories]
├── lean.json                # Lean engine configuration
├── download_data_from_yahoo.py  # Data download script
└── run-report.cmd           # Report generation script
```

## Setup

### Prerequisites

- [QuantConnect Lean CLI](https://www.quantconnect.com/docs/v2/lean-cli/getting-started/installation)
- Python 3.x
- Required Python packages:
  - `yfinance` (for data download)

### Installation

1. Install Lean CLI following the [official documentation](https://www.quantconnect.com/docs/v2/lean-cli/getting-started/installation)

2. Install Python dependencies:
```bash
pip install yfinance pandas
```

3. Download market data (if needed):
```bash
lean data download --help
```

## Usage

### Downloading Data

To download Bitcoin hourly data from Yahoo Finance:

```bash
python download_data_from_yahoo.py
```

This script downloads the last 730 days of hourly BTC-USD data and saves it to `Data/custom/btc_1h.csv`.

### Running Backtests

Run a backtest using the Lean CLI:

```bash
lean backtest "MyOfflineStrategy"
```

The backtest results will be saved in `MyOfflineStrategy/backtests/` with a timestamped directory.

### Generating Reports

After running a backtest, generate an HTML report:

```bash
lean report --backtest-results "MyOfflineStrategy/backtests/[timestamp]/[backtest-id].json"
```

Or use the provided script:

```bash
# Update the path in run-report.cmd with your latest backtest results
./run-report.cmd
```

### Research Notebook

Open the research notebook for interactive analysis:

```bash
lean research "MyOfflineStrategy"
```

## Custom Data Format

The strategy uses a custom `YahooHourlyCrypto` data class that reads from CSV files. The expected format:

```
YYYY-MM-DD HH:MM:SS,Close,High,Low,Open,Volume
```

Example:
```
2025-01-01 00:00:00,42000.5,42100.0,41900.0,41950.0,1234567.89
```

## Configuration

### Strategy Parameters

Edit `MyOfflineStrategy/main.py` to modify:
- EMA periods (lines 68-69)
- Stop loss percentage (line 73)
- Trailing stop percentage (line 74)
- Commission rate (line 65)
- Backtest dates (lines 56-57)
- Initial capital (line 58)

### Lean Configuration

Main configuration is in `lean.json`. Key settings:
- `data-folder`: Location of market data (default: "data")
- Environment settings for backtesting, paper trading, and live trading

## Strategy Components

### PercentageFeeModel

Custom fee model that charges a percentage-based commission on each trade (default: 0.1%).

### YahooHourlyCrypto

Custom data class that:
- Reads hourly Bitcoin data from CSV files
- Handles missing volume data (defaults to 100,000)
- Parses Yahoo Finance format

### Risk Management

- **Stop Loss**: Exits position if price drops 3% below entry
- **Trailing Stop**: Exits if price drops 5% below the highest price reached
- **EMA Signal**: Exits on bearish EMA crossover

## Performance Metrics

The strategy logs the following metrics at the end of each backtest:
- Total number of trades
- Win rate percentage
- Realized PnL
- Final portfolio value

## Data Sources

The project supports multiple data sources:
- **Custom Data**: Yahoo Finance (via `download_data_from_yahoo.py`)
- **QuantConnect Data Library**: Extensive market data for equities, futures, options, forex, crypto, and more
- Data is organized by asset class in the `Data/` directory

## Notes

- The strategy uses a warm-up period of 21 periods to initialize the slow EMA
- Volume data is artificially set to 100,000 if missing to ensure order execution
- The strategy is designed for hourly timeframes; adjust indicators and logic for other resolutions

## Resources

- [QuantConnect Lean Documentation](https://www.quantconnect.com/docs/v2/lean-cli)
- [QuantConnect Algorithm Documentation](https://www.quantconnect.com/docs/v2/writing-algorithms)
- [QuantConnect Data Library](https://www.quantconnect.com/docs/v2/lean-cli/datasets/downloading-data)

