#!/usr/bin/env python3
"""
Nifty 50 Stock Symbols (Indian NSE Market)
As of October 2025
"""

# Complete list of Nifty 50 constituents
NIFTY_50 = [
    # Top 10 by market cap
    'RELIANCE',      # Reliance Industries Ltd
    'TCS',           # Tata Consultancy Services Ltd
    'HDFCBANK',      # HDFC Bank Ltd
    'INFY',          # Infosys Ltd
    'ICICIBANK',     # ICICI Bank Ltd
    'HINDUNILVR',    # Hindustan Unilever Ltd
    'ITC',           # ITC Ltd
    'BHARTIARTL',    # Bharti Airtel Ltd
    'SBIN',          # State Bank of India
    'LT',            # Larsen & Toubro Ltd

    # Next 10
    'BAJFINANCE',    # Bajaj Finance Ltd
    'ASIANPAINT',    # Asian Paints Ltd
    'AXISBANK',      # Axis Bank Ltd
    'MARUTI',        # Maruti Suzuki India Ltd
    'TITAN',         # Titan Company Ltd
    'WIPRO',         # Wipro Ltd
    'SUNPHARMA',     # Sun Pharmaceutical Industries Ltd
    'ULTRACEMCO',    # UltraTech Cement Ltd
    'NESTLEIND',     # Nestle India Ltd
    'HCLTECH',       # HCL Technologies Ltd

    # Next 10
    'BAJAJFINSV',    # Bajaj Finserv Ltd
    'TATAMOTORS',    # Tata Motors Ltd
    'POWERGRID',     # Power Grid Corporation of India Ltd
    'NTPC',          # NTPC Ltd
    'ADANIPORTS',    # Adani Ports and Special Economic Zone Ltd
    'ONGC',          # Oil and Natural Gas Corporation Ltd
    'KOTAKBANK',     # Kotak Mahindra Bank Ltd
    'M&M',           # Mahindra & Mahindra Ltd
    'TECHM',         # Tech Mahindra Ltd
    'DRREDDY',       # Dr. Reddy's Laboratories Ltd

    # Next 10
    'TATASTEEL',     # Tata Steel Ltd
    'JSWSTEEL',      # JSW Steel Ltd
    'COALINDIA',     # Coal India Ltd
    'GRASIM',        # Grasim Industries Ltd
    'HINDALCO',      # Hindalco Industries Ltd
    'DIVISLAB',      # Divi's Laboratories Ltd
    'BAJAJ-AUTO',    # Bajaj Auto Ltd
    'HEROMOTOCO',    # Hero MotoCorp Ltd
    'EICHERMOT',     # Eicher Motors Ltd
    'SHREECEM',      # Shree Cement Ltd

    # Final 10
    'BPCL',          # Bharat Petroleum Corporation Ltd
    'CIPLA',         # Cipla Ltd
    'INDUSINDBK',    # IndusInd Bank Ltd
    'TATACONSUM',    # Tata Consumer Products Ltd
    'BRITANNIA',     # Britannia Industries Ltd
    'APOLLOHOSP',    # Apollo Hospitals Enterprise Ltd
    'ADANIENT',      # Adani Enterprises Ltd
    'HINDZINC',      # Hindustan Zinc Ltd
    'UPL',           # UPL Ltd
    'SBILIFE'        # SBI Life Insurance Company Ltd
]

# Quick scan - top 10 movers
NIFTY_QUICK = [
    'RELIANCE',
    'TCS',
    'HDFCBANK',
    'INFY',
    'ICICIBANK',
    'BHARTIARTL',
    'ITC',
    'SBIN',
    'LT',
    'BAJFINANCE'
]

# Sector-wise groups
NIFTY_SECTORS = {
    'it': ['TCS', 'INFY', 'WIPRO', 'HCLTECH', 'TECHM'],
    'banking': ['HDFCBANK', 'ICICIBANK', 'SBIN', 'AXISBANK', 'KOTAKBANK', 'INDUSINDBK'],
    'auto': ['MARUTI', 'TATAMOTORS', 'M&M', 'BAJAJ-AUTO', 'HEROMOTOCO', 'EICHERMOT'],
    'pharma': ['SUNPHARMA', 'DRREDDY', 'DIVISLAB', 'CIPLA'],
    'fmcg': ['HINDUNILVR', 'ITC', 'NESTLEIND', 'BRITANNIA', 'TATACONSUM'],
    'metals': ['TATASTEEL', 'JSWSTEEL', 'HINDALCO', 'COALINDIA', 'HINDZINC'],
    'energy': ['RELIANCE', 'ONGC', 'BPCL', 'NTPC', 'POWERGRID'],
    'finance': ['BAJFINANCE', 'BAJAJFINSV', 'SBILIFE']
}

def get_nifty_symbols(category='all'):
    """
    Get Nifty 50 symbols by category

    Args:
        category: 'all', 'quick', or sector name ('it', 'banking', etc.)

    Returns:
        List of stock symbols
    """
    if category == 'all':
        return NIFTY_50
    elif category == 'quick':
        return NIFTY_QUICK
    elif category in NIFTY_SECTORS:
        return NIFTY_SECTORS[category]
    else:
        return NIFTY_50

if __name__ == "__main__":
    print("Nifty 50 Stock Symbols\n")
    print(f"Total stocks: {len(NIFTY_50)}")
    print(f"Quick scan: {len(NIFTY_QUICK)}")
    print(f"Sectors available: {', '.join(NIFTY_SECTORS.keys())}")
