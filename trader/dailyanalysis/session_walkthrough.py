#!/usr/bin/env python3
"""
Live Session Walkthrough

Creates a detailed chronological narrative of the trading session:
- What happened minute by minute
- Why trades were taken/blocked
- Position management decisions
- Filter activations
"""

import json
import re
from datetime import datetime
from pathlib import Path
from collections import defaultdict
import pytz


class SessionWalkthrough:
    """
    Detailed walkthrough of live trading session

    Step 3 of EOD Analysis: Document exactly what happened and why
    """

    def __init__(self, date_str, log_dir='./logs'):
        """
        Initialize walkthrough analyzer

        Args:
            date_str: Date in YYYYMMDD format
            log_dir: Directory containing log files
        """
        self.date_str = date_str
        self.log_dir = Path(log_dir)

        # Load data sources
        self.log_lines = self._load_log()
        self.trades = self._load_trades()

        # Parsed events
        self.timeline = []
        self.key_events = []
        self.filter_blocks = defaultdict(list)
        self.position_events = defaultdict(list)

    def _load_log(self):
        """Load session log file"""
        log_file = self.log_dir / f"trader_{self.date_str}.log"
        if not log_file.exists():
            print(f"⚠️  Log file not found: {log_file}")
            return []

        with open(log_file, 'r') as f:
            return f.readlines()

    def _load_trades(self):
        """Load trades file"""
        trades_file = self.log_dir / f"trades_{self.date_str}.json"
        if not trades_file.exists():
            return []

        with open(trades_file, 'r') as f:
            return json.load(f)

    def generate_walkthrough(self):
        """Generate complete session walkthrough"""
        print(f"\n{'='*80}")
        print(f"LIVE SESSION WALKTHROUGH - {self.date_str}")
        print(f"{'='*80}")

        # Parse log into timeline
        self._parse_timeline()

        # Generate narrative sections
        self._print_session_overview()
        self._print_pre_market()
        self._print_market_open()
        self._print_trading_activity()
        self._print_position_management()
        self._print_session_close()
        self._print_key_learnings()

    def _parse_timeline(self):
        """Parse log into chronological events"""
        for line_num, line in enumerate(self.log_lines):
            # Extract timestamp if present
            timestamp_match = re.match(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
            if timestamp_match:
                timestamp = datetime.strptime(timestamp_match.group(1), '%Y-%m-%d %H:%M:%S')
            else:
                timestamp = None

            # Categorize events
            event = self._categorize_event(line, timestamp, line_num)
            if event:
                self.timeline.append(event)

    def _categorize_event(self, line, timestamp, line_num):
        """Categorize log line into event type"""
        event = {
            'timestamp': timestamp,
            'line_num': line_num,
            'raw': line.strip()
        }

        # Session start/end
        if 'Starting PS60 Live Trader' in line:
            event['type'] = 'SESSION_START'
            event['importance'] = 'HIGH'
            self.key_events.append(event)
            return event

        elif 'Market closed. Exiting' in line or 'EOD close triggered' in line:
            event['type'] = 'SESSION_END'
            event['importance'] = 'HIGH'
            self.key_events.append(event)
            return event

        # Position entries
        elif '🟢 LONG' in line:
            event['type'] = 'ENTRY_LONG'
            event['importance'] = 'HIGH'
            # Extract details
            match = re.search(r'🟢 LONG (\w+) @ \$([0-9.]+)', line)
            if match:
                event['symbol'] = match.group(1)
                event['price'] = float(match.group(2))
            self.key_events.append(event)
            return event

        elif '🔴 SHORT' in line:
            event['type'] = 'ENTRY_SHORT'
            event['importance'] = 'HIGH'
            match = re.search(r'🔴 SHORT (\w+) @ \$([0-9.]+)', line)
            if match:
                event['symbol'] = match.group(1)
                event['price'] = float(match.group(2))
            self.key_events.append(event)
            return event

        # Position management
        elif '💰 PARTIAL' in line:
            event['type'] = 'PARTIAL_PROFIT'
            event['importance'] = 'MEDIUM'
            match = re.search(r'💰 PARTIAL: (\w+)', line)
            if match:
                event['symbol'] = match.group(1)
            return event

        elif '🛡️' in line and 'Stop moved' in line:
            event['type'] = 'STOP_ADJUSTMENT'
            event['importance'] = 'MEDIUM'
            return event

        elif '🛑 STOP' in line:
            event['type'] = 'STOP_TRIGGERED'
            event['importance'] = 'HIGH'
            self.key_events.append(event)
            return event

        # Filter blocks
        elif '❌' in line and 'blocked' in line:
            event['type'] = 'FILTER_BLOCK'
            event['importance'] = 'LOW'
            # Extract symbol and reason
            match = re.search(r'❌ (\w+):.*blocked.*- (.+)', line)
            if match:
                symbol = match.group(1)
                reason = match.group(2).strip()
                self.filter_blocks[symbol].append({
                    'time': timestamp,
                    'reason': reason
                })
                event['symbol'] = symbol
                event['reason'] = reason
            return event

        # Entry path confirmation
        elif 'Entry Path:' in line:
            event['type'] = 'ENTRY_CONFIRMATION'
            event['importance'] = 'MEDIUM'
            match = re.search(r'Entry Path: (.+)', line)
            if match:
                event['path'] = match.group(1)
            return event

        # Market data updates
        elif 'Monitoring' in line and 'setups' in line:
            event['type'] = 'MONITORING_UPDATE'
            event['importance'] = 'LOW'
            return event

        # IBKR errors
        elif 'ERROR' in line or 'Error' in line:
            event['type'] = 'ERROR'
            event['importance'] = 'HIGH'
            self.key_events.append(event)
            return event

        return None

    def _print_session_overview(self):
        """Print high-level session overview"""
        print(f"\n📊 SESSION OVERVIEW")
        print(f"{'='*60}")

        # Find session bounds
        start_events = [e for e in self.timeline if e['type'] == 'SESSION_START']
        end_events = [e for e in self.timeline if e['type'] == 'SESSION_END']

        if start_events and end_events:
            start_time = start_events[0]['timestamp']
            end_time = end_events[-1]['timestamp']
            duration = (end_time - start_time).total_seconds() / 3600

            print(f"Session Start: {start_time.strftime('%I:%M:%S %p')}")
            print(f"Session End: {end_time.strftime('%I:%M:%S %p')}")
            print(f"Duration: {duration:.1f} hours")

        # Trade summary
        entry_events = [e for e in self.timeline if e['type'] in ['ENTRY_LONG', 'ENTRY_SHORT']]
        print(f"\nTotal Entries: {len(entry_events)}")

        if self.trades:
            winners = len([t for t in self.trades if t['pnl'] > 0])
            losers = len([t for t in self.trades if t['pnl'] < 0])
            total_pnl = sum(t['pnl'] for t in self.trades)

            print(f"Winners: {winners}")
            print(f"Losers: {losers}")
            print(f"Total P&L: ${total_pnl:.2f}")

        # Filter blocks
        total_blocks = sum(len(blocks) for blocks in self.filter_blocks.values())
        print(f"\nTotal Filter Blocks: {total_blocks}")
        print(f"Unique Symbols Blocked: {len(self.filter_blocks)}")

    def _print_pre_market(self):
        """Print pre-market setup phase"""
        print(f"\n🌅 PRE-MARKET SETUP (9:00-9:30 AM)")
        print(f"{'='*60}")

        # Find pre-market events
        pre_market_events = []
        for event in self.timeline:
            if event['timestamp'] and event['timestamp'].hour < 9 or \
               (event['timestamp'].hour == 9 and event['timestamp'].minute < 30):
                pre_market_events.append(event)

        if not pre_market_events:
            print("No pre-market activity recorded")
            return

        # Key pre-market events
        for event in pre_market_events:
            if event['importance'] in ['HIGH', 'MEDIUM']:
                time_str = event['timestamp'].strftime('%I:%M:%S %p') if event['timestamp'] else 'N/A'
                print(f"  {time_str}: {event['raw'][:80]}")

    def _print_market_open(self):
        """Print market open activity"""
        print(f"\n🔔 MARKET OPEN (9:30-10:00 AM)")
        print(f"{'='*60}")

        # Find market open events
        open_events = []
        for event in self.timeline:
            if event['timestamp'] and \
               event['timestamp'].hour == 9 and event['timestamp'].minute >= 30:
                open_events.append(event)
            elif event['timestamp'] and event['timestamp'].hour == 10 and event['timestamp'].minute == 0:
                break

        if not open_events:
            print("No market open activity")
            return

        # Summarize activity
        entries = [e for e in open_events if e['type'] in ['ENTRY_LONG', 'ENTRY_SHORT']]
        blocks = [e for e in open_events if e['type'] == 'FILTER_BLOCK']

        print(f"\nOpening Activity:")
        print(f"  Entries: {len(entries)}")
        print(f"  Filter Blocks: {len(blocks)}")

        # List entries
        if entries:
            print(f"\n  Positions Opened:")
            for entry in entries:
                time_str = entry['timestamp'].strftime('%I:%M %p')
                symbol = entry.get('symbol', 'UNKNOWN')
                price = entry.get('price', 0)
                side = 'LONG' if entry['type'] == 'ENTRY_LONG' else 'SHORT'
                print(f"    {time_str}: {side} {symbol} @ ${price:.2f}")

        # Top filter blocks
        if blocks:
            block_reasons = defaultdict(int)
            for block in blocks:
                reason = block.get('reason', 'Unknown')
                block_reasons[reason] += 1

            print(f"\n  Top Blocking Reasons:")
            for reason, count in sorted(block_reasons.items(), key=lambda x: x[1], reverse=True)[:3]:
                print(f"    {reason}: {count} times")

    def _print_trading_activity(self):
        """Print main trading hours activity"""
        print(f"\n📈 MAIN TRADING HOURS (10:00 AM - 3:00 PM)")
        print(f"{'='*60}")

        # Group activity by hour
        hourly_activity = defaultdict(lambda: {'entries': 0, 'exits': 0, 'blocks': 0})

        for event in self.timeline:
            if not event['timestamp']:
                continue

            hour = event['timestamp'].hour
            if hour < 10 or hour >= 15:
                continue

            if event['type'] in ['ENTRY_LONG', 'ENTRY_SHORT']:
                hourly_activity[hour]['entries'] += 1
            elif event['type'] in ['STOP_TRIGGERED', 'PARTIAL_PROFIT']:
                hourly_activity[hour]['exits'] += 1
            elif event['type'] == 'FILTER_BLOCK':
                hourly_activity[hour]['blocks'] += 1

        # Print hourly summary
        print(f"\n{'Hour':<8} {'Entries':>10} {'Exits':>10} {'Blocks':>10}")
        print(f"{'-'*38}")

        for hour in range(10, 15):
            activity = hourly_activity[hour]
            hour_str = f"{hour}:00"
            print(f"{hour_str:<8} {activity['entries']:>10} {activity['exits']:>10} {activity['blocks']:>10}")

        # Highlight key trades during this period
        print(f"\n📌 Key Trades:")
        key_trades = [e for e in self.key_events
                      if e['type'] in ['ENTRY_LONG', 'ENTRY_SHORT']
                      and e['timestamp']
                      and 10 <= e['timestamp'].hour < 15]

        for trade in key_trades[:5]:  # Top 5
            time_str = trade['timestamp'].strftime('%I:%M %p')
            symbol = trade.get('symbol', 'UNKNOWN')
            side = 'LONG' if trade['type'] == 'ENTRY_LONG' else 'SHORT'

            # Find corresponding trade result
            trade_result = next((t for t in self.trades if t['symbol'] == symbol), None)
            if trade_result:
                pnl = trade_result['pnl']
                result = f"${pnl:+.2f}" if pnl != 0 else "Scratch"
            else:
                result = "Open"

            print(f"  {time_str}: {side} {symbol} → {result}")

    def _print_position_management(self):
        """Print position management actions"""
        print(f"\n🎯 POSITION MANAGEMENT")
        print(f"{'='*60}")

        # Count management actions
        partials = [e for e in self.timeline if e['type'] == 'PARTIAL_PROFIT']
        stop_adjustments = [e for e in self.timeline if e['type'] == 'STOP_ADJUSTMENT']
        stops_hit = [e for e in self.timeline if e['type'] == 'STOP_TRIGGERED']

        print(f"\nManagement Actions:")
        print(f"  Partial Profits Taken: {len(partials)}")
        print(f"  Stop Adjustments: {len(stop_adjustments)}")
        print(f"  Stops Triggered: {len(stops_hit)}")

        # Detail partial profits
        if partials:
            print(f"\n  Partial Profit Timeline:")
            for partial in partials[:5]:  # Top 5
                if partial['timestamp']:
                    time_str = partial['timestamp'].strftime('%I:%M %p')
                    symbol = partial.get('symbol', 'UNKNOWN')
                    print(f"    {time_str}: {symbol} - Took 50% profit")

        # 5-minute rule exits
        five_min_exits = [t for t in self.trades if t.get('reason') == '5MIN_RULE']
        if five_min_exits:
            print(f"\n  5-Minute Rule Exits: {len(five_min_exits)}")
            total_5min_pnl = sum(t['pnl'] for t in five_min_exits)
            print(f"    Total P&L from 5-min exits: ${total_5min_pnl:.2f}")
            if total_5min_pnl < -500:
                print(f"    ⚠️  5-minute rule cost ${abs(total_5min_pnl):.2f} - review threshold")

    def _print_session_close(self):
        """Print end-of-day activity"""
        print(f"\n🌆 SESSION CLOSE (3:00-4:00 PM)")
        print(f"{'='*60}")

        # Find late-day events
        close_events = []
        for event in self.timeline:
            if event['timestamp'] and event['timestamp'].hour >= 15:
                close_events.append(event)

        # EOD closes
        eod_trades = [t for t in self.trades if t.get('reason') == 'EOD']
        if eod_trades:
            print(f"\nEOD Position Closes: {len(eod_trades)}")
            eod_pnl = sum(t['pnl'] for t in eod_trades)
            print(f"Total P&L from EOD closes: ${eod_pnl:.2f}")

            # List EOD positions
            print(f"\n  Positions closed at EOD:")
            for trade in eod_trades:
                symbol = trade['symbol']
                pnl = trade['pnl']
                print(f"    {symbol}: ${pnl:+.2f}")

    def _print_key_learnings(self):
        """Print key learnings and recommendations"""
        print(f"\n💡 KEY LEARNINGS & RECOMMENDATIONS")
        print(f"{'='*60}")

        learnings = []

        # Check for pattern in filter blocks
        if self.filter_blocks:
            most_blocked = max(self.filter_blocks.items(), key=lambda x: len(x[1]))
            symbol, blocks = most_blocked
            if len(blocks) > 5:
                learnings.append(f"• {symbol} was blocked {len(blocks)} times - consider blacklisting")

        # Check for early exit patterns
        quick_exits = [t for t in self.trades if t.get('reason') == '5MIN_RULE']
        if len(quick_exits) > len(self.trades) * 0.5:
            learnings.append("• Over 50% of trades hit 5-minute rule - confirmation may be too strict")

        # Check for missed opportunities
        total_blocks = sum(len(blocks) for blocks in self.filter_blocks.values())
        total_trades = len(self.trades)
        if total_blocks > total_trades * 3:
            learnings.append(f"• {total_blocks} filter blocks vs {total_trades} trades - possible over-filtering")

        # Position sizing issues
        position_blocks = sum(1 for blocks in self.filter_blocks.values()
                            for block in blocks
                            if 'Position too large' in block.get('reason', ''))
        if position_blocks > 10:
            learnings.append(f"• {position_blocks} 'Position too large' blocks - implement adaptive sizing")

        # Print learnings
        if learnings:
            for learning in learnings:
                print(learning)
        else:
            print("• Session performed as expected - no major issues identified")

        # Performance assessment
        if self.trades:
            total_pnl = sum(t['pnl'] for t in self.trades)
            win_rate = len([t for t in self.trades if t['pnl'] > 0]) / len(self.trades) * 100

            print(f"\n📊 Performance Assessment:")
            if total_pnl > 1000:
                print(f"  ✅ Profitable session (${total_pnl:.2f}) - strategy working")
            elif total_pnl > 0:
                print(f"  ✓ Marginally profitable (${total_pnl:.2f}) - room for improvement")
            else:
                print(f"  ❌ Losing session (${total_pnl:.2f}) - review filters and execution")

            if win_rate > 50:
                print(f"  ✅ Good win rate ({win_rate:.1f}%) - entry selection working")
            elif win_rate > 35:
                print(f"  ✓ Acceptable win rate ({win_rate:.1f}%) - normal for trend following")
            else:
                print(f"  ⚠️  Low win rate ({win_rate:.1f}%) - review entry criteria")

    def save_walkthrough(self):
        """Save walkthrough to file"""
        output = {
            'date': self.date_str,
            'key_events': [
                {
                    'time': e['timestamp'].isoformat() if e['timestamp'] else None,
                    'type': e['type'],
                    'description': e['raw'][:200]
                }
                for e in self.key_events
            ],
            'filter_blocks': dict(self.filter_blocks),
            'trades': self.trades
        }

        output_file = Path(f'logs/session_walkthrough_{self.date_str}.json')
        with open(output_file, 'w') as f:
            json.dump(output, f, indent=2, default=str)

        print(f"\n📄 Walkthrough saved to: {output_file}")
        return output_file


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("Usage: python session_walkthrough.py YYYYMMDD")
        print("Example: python session_walkthrough.py 20251007")
        sys.exit(1)

    date_str = sys.argv[1]

    walkthrough = SessionWalkthrough(date_str)
    walkthrough.generate_walkthrough()
    walkthrough.save_walkthrough()