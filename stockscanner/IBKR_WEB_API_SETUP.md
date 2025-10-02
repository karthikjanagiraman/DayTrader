# IBKR Web API Setup Guide

## Overview

The scanner now uses Interactive Brokers Client Portal Web API, which provides REST endpoints and WebSocket streaming for real-time market data.

## Prerequisites

1. **Active IBKR Account** with:
   - API access enabled
   - Market data subscriptions
   - Valid login credentials

2. **IBKR Client Portal Gateway** installed

## Installation Steps

### 1. Download Client Portal Gateway

1. Log in to your IBKR account
2. Go to Account Management → Settings → API
3. Download "Client Portal Gateway" for your OS
4. Extract the downloaded archive to a folder (e.g., `~/ibkr-gateway/`)

### 2. Configure Gateway

Edit `conf.yaml` in the gateway folder:

```yaml
listenPort: 5000
listenHost: 127.0.0.1
sslCert: 'certs/certificate.pem'
sslKey: 'certs/private_key.pem'
```

### 3. Start Client Portal Gateway

```bash
cd ~/ibkr-gateway/
./bin/run.sh root/conf.yaml  # Mac/Linux
# or
bin\run.bat root\conf.yaml   # Windows
```

The gateway will:
1. Start on https://localhost:5000
2. Open a browser for authentication
3. Require you to log in with your IBKR credentials

### 4. Authenticate

1. Browser opens automatically to https://localhost:5000
2. Enter IBKR username and password
3. Complete two-factor authentication if enabled
4. Keep the gateway running

## Using the Scanner with Web API

### Configuration

The scanner is configured to use Web API by default in `config/scanner_config.yaml`:

```yaml
ibkr:
  use_web_api: true
  web_api_url: "https://localhost:5000/v1/api"
```

### Running the Scanner

With the Client Portal Gateway running and authenticated:

```bash
# Scan historical date
python src/scanner.py --date 2024-09-26

# Live pre-market scan
python src/scanner.py --live
```

## API Endpoints Used

The scanner uses these Client Portal API endpoints:

- `/portal/iserver/auth/status` - Check authentication
- `/portal/iserver/accounts` - Get account info
- `/portal/iserver/secdef/search` - Search for contracts
- `/portal/iserver/marketdata/history` - Historical data
- `/portal/iserver/marketdata/snapshot` - Real-time quotes
- `/portal/iserver/marketdata/news` - News data

## Troubleshooting

### Gateway Not Running

Error: `IBKR Client Portal not accessible`

Solution:
1. Start the Client Portal Gateway
2. Ensure it's running on port 5000
3. Check firewall settings

### Authentication Failed

Error: `Failed to authenticate with IBKR Web API`

Solution:
1. Log in via browser at https://localhost:5000
2. Complete authentication
3. Keep gateway session active

### No Market Data

Error: `No historical data for symbol`

Solution:
1. Verify market data subscriptions
2. Check symbol is valid
3. Ensure account has permissions

### SSL Certificate Errors

The Web API uses self-signed certificates. The scanner handles this automatically, but if issues persist:

1. Accept the certificate in your browser
2. Or temporarily disable SSL verification (not recommended for production)

## Rate Limits

- Max 50 concurrent requests
- 0.1 second delay between requests
- Batch operations limited to 10 symbols

## Session Management

- Gateway sessions timeout after 24 hours
- Requires daily re-authentication
- Keep gateway running during market hours

## Security Notes

1. **Never share** your gateway URL publicly
2. **Always use** localhost for gateway
3. **Keep credentials** secure
4. **Monitor access** logs regularly

## Additional Resources

- [IBKR Client Portal API Docs](https://www.interactivebrokers.com/api/doc.html)
- [Web API Reference](https://www.interactivebrokers.com/api/doc.html#tag/Trading)
- [Market Data Endpoints](https://www.interactivebrokers.com/api/doc.html#tag/Market-Data)

---

**Important**: The scanner will ONLY work with real data from IBKR. No simulated or fake data will be used. If the gateway is not running or authenticated, the scanner will fail with an appropriate error message.