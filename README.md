# Hedge - Crypto Pair Trading Analysis Tool

A desktop application for discovering and analyzing cryptocurrency pair trading opportunities on Hyperliquid.

## Features

- 🔍 **Pair Discovery** - Scan and filter crypto pairs by correlation, cointegration, and signals
- 📊 **Technical Analysis** - Correlation, Z-Score, Half-Life, Cointegration testing
- 📈 **Interactive Charts** - Price ratio, Z-Score, Spread, Rolling Correlation, and Volatility charts
- 💼 **Watchlist** - Save and monitor your favorite trading pairs
- 🔄 **Auto Data Updates** - Background service keeps market data fresh
- 🎨 **Modern UI** - Built with PyQt6 and QML with dark theme

## Tech Stack

- **Frontend**: PyQt6 + QML
- **Backend**: Python 3.13
- **Database**: SQLite
- **API**: Hyperliquid API
- **Analysis**: NumPy, Pandas, Statsmodels

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/hedge.git
cd hedge
```

2. Create virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install PyQt6 pandas numpy statsmodels requests sqlalchemy
```

4. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your settings
```

5. Run the application:
```bash
python desktop/main.py
```

## Usage

### Discovery Page
1. Select a reference coin (e.g., HYPE, BTC)
2. Choose timeframe (Scalping, Intraday, Swing)
3. Browse pairs sorted by correlation, cointegration, or signals
4. Click "Analyze" to view detailed analysis

### Analysis Page
- View correlation, Z-score, half-life, cointegration status
- Analyze interactive charts with zoom/pan
- Switch timeframes (5min, 1hour, 4hour)
- Adjust chart size for better visibility

### Watchlist
- Add pairs from Discovery page
- Monitor key metrics at a glance
- Quick access to analysis

## Data Updates

The app includes a background data updater that keeps OHLCV data fresh:
- Updates on startup
- Configurable update intervals
- Thread-safe SQLite write queue

## Project Structure

```
hedge/
├── desktop/
│   ├── main.py                 # Application entry point
│   ├── qml/                    # UI files
│   │   ├── MainApp.qml
│   │   ├── AnalysisView.qml
│   │   ├── DiscoveryView.qml
│   │   └── WatchlistView.qml
│   └── src/qml_bridge/         # Python-QML bridge models
├── src/
│   ├── api/                    # API clients (Hyperliquid)
│   ├── database/               # Database models and queries
│   ├── services/               # Background services
│   └── utils/                  # Utilities
└── data/                       # SQLite database and cache
```

## License

MIT License - See LICENSE file for details

## Contributing

Contributions welcome! Please open an issue or PR.

## Disclaimer

This tool is for educational and research purposes only. Not financial advice. Trade at your own risk.
