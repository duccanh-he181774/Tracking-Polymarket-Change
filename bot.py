"""
Polymarket Market Tracker Bot
Monitors markets and sends alerts on significant price movements
"""

from market_tracker import MarketTracker
from websocket_tracker import WebSocketMarketTracker
from config import USE_WEBSOCKET
import sys

def main():
    """Main entry point for the bot"""
    print("""
╔════════════════════════════════════════════════════════════╗
║         POLYMARKET MARKET TRACKER BOT                      ║
║                                                            ║
║  Monitors market price changes and sends alerts           ║
║  Press Ctrl+C to stop the bot                             ║
╚════════════════════════════════════════════════════════════╝
    """)
    
    try:
        if USE_WEBSOCKET:
            print("🔌 Using WebSocket mode (Real-time updates)")
            tracker = WebSocketMarketTracker()
        else:
            print("🔄 Using Polling mode (Periodic checks)")
            tracker = MarketTracker()
        
        tracker.run()
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
