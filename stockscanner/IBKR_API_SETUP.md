# IBKR API Configuration Requirements

## Current Status
- ✅ TWS is running (port 7497 is open)
- ❌ API connections are timing out
- ❌ reqHistoricalData calls hang indefinitely
- ❌ Client Portal not responding on port 5000

## Required TWS Configuration

### 1. Enable API Connections in TWS
1. Open TWS
2. Go to **File → Global Configuration → API → Settings**
3. Check these settings:
   - ✅ **Enable ActiveX and Socket Clients** (MUST be checked)
   - ✅ Socket port: **7497** (for paper trading)
   - ✅ **Trusted IP Addresses**: Add **127.0.0.1**
   - ❌ **Read-Only API** (MUST be unchecked)
   - ✅ **Download open orders on connection**
   - ✅ **Send account window summary messages**

### 2. API Precautions Tab
1. Still in API Settings, go to **Precautions** tab
2. Uncheck or adjust:
   - **Bypass Order Precautions for API Orders** (optional)
   - Set **API Order Message Timeout** to at least 10 seconds

### 3. Market Data Settings
1. Go to **File → Global Configuration → Market Data → Options**
2. Check:
   - **Download open orders on connection**
   - **Use Regular Trading Hours only** (uncheck for extended hours)

### 4. Connection Settings
1. Go to **File → Global Configuration → Connection**
2. Ensure:
   - **Auto Logoff Timer** is disabled or set to a long duration
   - **Lock and Exit** is unchecked

## Troubleshooting Steps Taken

1. **Port Check**: Port 7497 is open and listening ✅
2. **Socket Test**: Can connect to port but API doesn't respond ❌
3. **Multiple Client IDs**: Tried IDs 99-9999, all timeout ❌
4. **Different Libraries**: Used ib_insync with various configurations ❌
5. **Event Loop Management**: Tried async, sync, and util.startLoop() ❌
6. **Client Portal**: Port 5000 open but not responding to API calls ❌

## Root Cause
The API is not properly enabled in TWS settings. Even though the port is open, TWS is not accepting API connections, likely because:
1. "Enable ActiveX and Socket Clients" is not checked
2. 127.0.0.1 is not in the trusted IP list
3. Read-Only API might be enabled

## Solution
Please configure TWS with the settings above and restart TWS. Once configured:
1. The scanner will be able to connect
2. Historical data requests will work
3. The scanner can find tomorrow's trading setups

## Test Command
After configuring TWS, test with:
```bash
python3 test_connection.py
```

If successful, run the full scanner:
```bash
python3 -m src.scanner
# or
python3 scanner_tomorrow.py
```