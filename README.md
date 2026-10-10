# Option Intelligence Free — Paper Trading

A new-from-scratch free intraday option-buyer intelligence dashboard.

## What it includes

- NIFTY / BANKNIFTY switch
- 5-minute market candles
- EMA 9 / EMA 21
- VWAP
- RSI
- ATR
- ADX
- volume ratio
- NSE option-chain attempt for OI, OI change, IV and PCR
- BUY CALL / BUY PUT / WAIT decision engine
- confidence score
- suggested underlying stop-loss / target
- client-side paper trading with virtual capital
- trade log and P&L
- no broker order is placed

## Data sources

1. Yahoo Finance 5-minute index candles for the underlying.
2. NSE option-chain endpoint for option-chain/OI data.

These public web sources can reject automated/cloud requests. Yahoo's NIFTY/BANKNIFTY spot-index candles commonly report zero volume; in that case VWAP and volume ratio are intentionally shown as unavailable instead of fabricated. NSE may block option-chain requests from cloud hosting, so PCR/OI/IV can remain unavailable until a permitted reliable data source is connected. The application deliberately shows unavailable status instead of inventing prices.

## Deploy on Render

1. Create a new GitHub repository.
2. Upload all files/folders from this project.
3. In Render choose New + -> Web Service.
4. Connect the GitHub repository.
5. Runtime: Python.
6. Build command:
   `pip install -r requirements.txt`
7. Start command:
   `uvicorn app:app --host 0.0.0.0 --port $PORT`
8. Choose the Free plan and deploy.

## Important

Paper trades are simulated only. No broker account, API key, or real order is used.

For reliable production-grade live option trading data, a licensed market-data/broker API should eventually replace the public endpoints.
