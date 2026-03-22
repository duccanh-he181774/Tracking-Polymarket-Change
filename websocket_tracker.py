import websocket
import json
import threading
import time
import requests
from typing import Dict, Set
from notifier import Notifier
from config import (
    GAMMA_API_URL,
    WEBSOCKET_URL,
    WEBSOCKET_PING_INTERVAL,
    CATEGORY,
    PRICE_CHANGE_THRESHOLD,
    MIN_VOLUME,
    MAX_MARKETS_TO_SUBSCRIBE,
    PRICE_HISTORY_FILE,
    USE_PROXY,
    PROXY_URL,
    REFETCH_INTERVAL,
    ENABLE_PINNED_MONITOR,
    HIGH_RATE_THRESHOLD_MIN,
    HIGH_RATE_THRESHOLD_MAX,
    PINNED_MESSAGE_UPDATE_INTERVAL
)

class WebSocketMarketTracker:
    """Real-time market tracking using WebSocket"""
    
    def __init__(self):
        self.notifier = Notifier()
        self.price_history: Dict[str, float] = {}
        self.market_info: Dict[str, dict] = {}
        self.subscribed_tokens: Set[str] = set()
        self.ws = None
        self.running = False
        self.ping_thread = None
        self.refetch_thread = None
        self.last_refetch_time = time.time()
        
        # Monitor thread for pinned message
        self.monitor_running = False
        self.monitor_thread = None
        self.latest_markets = []  # Store latest markets for monitor
        
        # HTTP session for initial market fetching
        self.session = requests.Session()
        if USE_PROXY:
            self.session.proxies.update({"http": PROXY_URL, "https": PROXY_URL})
        
        self.load_price_history()
    
    def load_price_history(self):
        """Load previous price history from file"""
        try:
            with open(PRICE_HISTORY_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.price_history = data.get('price_history', {})
                self.market_info = data.get('market_info', {})
            self.notifier.log_info(f"Loaded {len(self.price_history)} markets from history")
        except FileNotFoundError:
            self.notifier.log_info("No previous price history found, starting fresh")
        except Exception as e:
            self.notifier.log_error(f"Error loading price history: {e}")
    
    def should_filter_market(self, market: dict) -> bool:
        """Check if market should be filtered out (Bitcoin price predictions or sports)
        Uses event tags from API for accurate filtering instead of keywords
        """
        try:
            # Get event title for additional context
            event_title = market.get('event_title', '').lower()
            question = market.get('question', '').lower()
            
            # Method 1: Check event tags (from event data added to market)
            # This is the most reliable method as tags come directly from API
            event_tags = market.get('event_tags', [])
            if event_tags:
                for tag in event_tags:
                    if isinstance(tag, dict):
                        tag_slug = tag.get('slug', '').lower()
                        tag_label = tag.get('label', '').lower()
                        
                        # Filter sports by tag slug
                        sports_tag_slugs = ['sports', 'soccer', 'football', 'basketball', 'nba', 
                                           'mlb', 'nfl', 'nhl', 'tennis', 'golf', 'boxing', 'mma', 
                                           'ufc', 'cricket', 'hockey', 'epl', 'games']
                        if tag_slug in sports_tag_slugs:
                            return True
                        
                        # Filter crypto price predictions
                        # Look for crypto tags combined with price-related questions
                        crypto_tag_slugs = ['crypto', 'bitcoin', 'btc', 'ethereum', 'eth', 
                                           'cryptocurrency', 'crypto-prices']
                        if tag_slug in crypto_tag_slugs:
                            # Check if it's a price prediction
                            price_keywords = ['price', 'above', 'below', '$', 'reach', 'hit', 
                                            'trading', 'trade above', 'trade below']
                            if any(keyword in question or keyword in event_title 
                                   for keyword in price_keywords):
                                return True
            
            # Method 2: Fallback to keyword matching if no tags available
            # (for cases where event_tags might not be passed)
            
            # Filter Bitcoin/crypto price predictions by question content
            if any(crypto_word in question or crypto_word in event_title 
                   for crypto_word in ['bitcoin', 'btc', 'ethereum', 'eth']):
                if any(price_word in question or price_word in event_title 
                       for price_word in ['price', 'above', 'below', '$', 'reach', 'trade above']):
                    return True
            
            # Filter sports by common keywords (fallback)
            sports_keywords = ['nfl', 'nba', 'mlb', 'nhl', 'premier league', 'champions league',
                              'world cup', 'super bowl', 'playoffs', 'vs.', 'vs ']
            if any(keyword in event_title for keyword in sports_keywords):
                return True
            
            return False
        except Exception as e:
            # If there's an error checking, don't filter it out
            return False
    
    def cleanup_closed_markets(self, active_market_ids: set):
        """Remove closed markets from price history to prevent bloat"""
        try:
            # Find markets in history that are no longer active
            tracked_ids = set(self.price_history.keys())
            closed_ids = tracked_ids - active_market_ids
            
            if closed_ids:
                # Remove closed markets from all tracking dictionaries
                for market_id in closed_ids:
                    self.price_history.pop(market_id, None)
                    self.market_info.pop(market_id, None)
                
                self.notifier.log_info(f"🧹 Cleaned up {len(closed_ids)} closed markets from history")
                # Save after cleanup
                self.save_price_history()
        except Exception as e:
            self.notifier.log_error(f"Error cleaning up closed markets: {e}")
    
    def save_price_history(self):
        """Save current price history to file"""
        try:
            from datetime import datetime
            data = {
                'price_history': self.price_history,
                'market_info': self.market_info,
                'last_updated': datetime.now().isoformat()
            }
            with open(PRICE_HISTORY_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.notifier.log_error(f"Error saving price history: {e}")
    
    def fetch_markets_to_track(self) -> list:
        """Fetch top markets from category to track"""
        try:
            # Use Events endpoint to get current active markets
            url = f"{GAMMA_API_URL}/events"
            params = {
                "tag": CATEGORY,
                "limit": 100,  # Fetch more events to get enough markets
                "closed": "false",
                "order": "volume24hr",
                "ascending": "false"
            }
            
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            events = response.json()
            
            # Extract all markets from events
            all_markets = []
            for event in events:
                event_markets = event.get('markets', [])
                # Get event tags for filtering
                event_tags = event.get('tags', [])
                for market in event_markets:
                    # Add event context
                    market['event_title'] = event.get('title', '')
                    market['event_slug'] = event.get('slug', '')
                    market['event_tags'] = event_tags  # Add tags for filtering
                    
                    # Use event volume if market doesn't have volume
                    if not market.get('volume'):
                        market['volume'] = event.get('volume', 0)
                    
                    all_markets.append(market)
            
            # Filter by volume and sort
            filtered_markets = [
                m for m in all_markets 
                if float(m.get('volume', 0)) >= MIN_VOLUME
            ]
            
            # Sort by volume descending
            filtered_markets.sort(
                key=lambda m: float(m.get('volume', 0)), 
                reverse=True
            )
            
            # Take top N markets
            top_markets = filtered_markets[:MAX_MARKETS_TO_SUBSCRIBE]
            
            self.notifier.log_info(
                f"Found {len(all_markets)} total markets, "
                f"filtered to {len(filtered_markets)}, "
                f"subscribing to top {len(top_markets)}"
            )
            
            return top_markets
            
        except Exception as e:
            self.notifier.log_error(f"Error fetching markets: {e}")
            return []
    
    def on_open(self, ws):
        """WebSocket connection opened"""
        self.notifier.log_info("WebSocket connected!")
        
        # Fetch and subscribe to markets
        self.subscribe_to_markets()
        
        # Start ping thread
        self.start_ping_thread()
        
        # Start refetch thread for periodic market discovery
        self.start_refetch_thread()
    
    def subscribe_to_markets(self):
        """Fetch markets and subscribe to their updates"""
        # Fetch markets to track
        markets = self.fetch_markets_to_track()
        
        # Store latest markets for monitor
        self.latest_markets = markets
        
        if not markets:
            self.notifier.log_error("No markets found to subscribe")
            return
        
        # Build subscription message
        assets_ids = []
        new_markets_count = 0
        filtered_count = 0
        active_market_ids = set()
        
        for market in markets:
            # Store market info
            market_id = market.get('id')
            if not market_id:
                continue
            
            # Track active market IDs for cleanup
            active_market_ids.add(market_id)
            
            # Filter out Bitcoin price predictions and sports
            if self.should_filter_market(market):
                filtered_count += 1
                continue
            
            # Check if this is a new market
            is_new = market_id not in self.market_info
            if is_new:
                new_markets_count += 1
            
            self.market_info[market_id] = {
                'question': market.get('question', 'Unknown'),
                'event_title': market.get('event_title', ''),
                'event_slug': market.get('event_slug', ''),
                'slug': market.get('slug', ''),
                'volume': float(market.get('volume', 0))
            }
            
            # Get token IDs for subscription
            tokens = market.get('tokens', [])
            for token in tokens:
                token_id = token.get('token_id') or token.get('tokenId')
                if token_id:
                    assets_ids.append(token_id)
                    self.subscribed_tokens.add(token_id)
        
        # Cleanup closed markets
        self.cleanup_closed_markets(active_market_ids)
        
        # Send subscription message if we have a websocket connection
        if self.ws and assets_ids:
            subscription_msg = {
                "auth": {},
                "markets": [],
                "assets_ids": assets_ids,
                "type": "market"
            }
            
            log_msg = f"Subscribing to {len(assets_ids)} token IDs from {len(markets)} markets"
            if filtered_count > 0:
                log_msg += f" (🚫 {filtered_count} filtered)"
            if new_markets_count > 0:
                log_msg += f" ({new_markets_count} new)"
            self.notifier.log_info(log_msg)
            
            try:
                self.ws.send(json.dumps(subscription_msg))
                self.last_refetch_time = time.time()
                # Save after successful subscription
                self.save_price_history()
            except Exception as e:
                self.notifier.log_error(f"Error sending subscription: {e}")
    
    def on_message(self, ws, message):
        """Handle incoming WebSocket message"""
        try:
            data = json.loads(message)
            
            # Handle different message types
            message_type = data.get('event_type') or data.get('type')
            
            if message_type == 'price_change' or message_type == 'last_trade_price':
                self.handle_price_update(data)
            elif message_type == 'book':
                # Orderbook update - can extract price from best bid/ask
                self.handle_book_update(data)
            # Ignore other message types for now
            
        except json.JSONDecodeError:
            pass  # Ignore non-JSON messages (like pongs)
        except Exception as e:
            self.notifier.log_error(f"Error handling message: {e}")
    
    def handle_price_update(self, data):
        """Handle price update from WebSocket"""
        try:
            asset_id = data.get('asset_id') or data.get('token_id')
            price = data.get('price')
            
            if not asset_id or price is None:
                return
            
            price = float(price)
            
            # Find market info for this token
            market_id = self.find_market_by_token(asset_id)
            if not market_id:
                return
            
            # Check price change
            if market_id in self.price_history:
                previous_price = self.price_history[market_id]
                
                # Calculate absolute price change (percentage points)
                # Example: 0.01 (1%) to 0.11 (11%) = 0.10 change (10 percentage points)
                price_change = price - previous_price
                
                # Check if absolute change exceeds threshold
                if abs(price_change) >= PRICE_CHANGE_THRESHOLD:
                        direction = "UP" if price_change > 0 else "DOWN"
                        
                        # Get market info
                        market_info = self.market_info.get(market_id, {})
                        
                        # Prepare alert data
                        market_data = {
                            'question': market_info.get('question', 'Unknown'),
                            'event_title': market_info.get('event_title', ''),
                            'event_slug': market_info.get('event_slug', ''),
                            'slug': market_info.get('slug', ''),
                            'current_price': price,
                            'previous_price': previous_price,
                            'volume': market_info.get('volume', 0),
                            'id': market_id
                        }
                        
                        # Send alert
                        self.notifier.send_alert(market_data, price_change, direction)
                        
                        # Save history after alert
                        self.save_price_history()
            
            # Update price history
            self.price_history[market_id] = price
            
        except Exception as e:
            self.notifier.log_error(f"Error handling price update: {e}")
    
    def handle_book_update(self, data):
        """Handle orderbook update - extract best bid/ask as price"""
        try:
            asset_id = data.get('asset_id') or data.get('token_id')
            
            if not asset_id:
                return
            
            # Extract best bid and ask
            bids = data.get('bids', [])
            asks = data.get('asks', [])
            
            if not bids or not asks:
                return
            
            # Mid price = (best_bid + best_ask) / 2
            best_bid = float(bids[0].get('price', 0))
            best_ask = float(asks[0].get('price', 0))
            
            if best_bid == 0 or best_ask == 0:
                return
            
            mid_price = (best_bid + best_ask) / 2
            
            # Create a price update event
            self.handle_price_update({
                'asset_id': asset_id,
                'price': mid_price
            })
            
        except Exception as e:
            self.notifier.log_error(f"Error handling book update: {e}")
    
    def find_market_by_token(self, token_id):
        """Find market ID from token ID"""
        # This is a simplified approach - in reality you'd need to maintain
        # a token_id -> market_id mapping from the initial fetch
        # For now, we'll use the market_id as a key
        # You might need to adjust based on actual WebSocket message format
        return token_id  # Placeholder
    
    def on_error(self, ws, error):
        """Handle WebSocket error"""
        self.notifier.log_error(f"WebSocket error: {error}")
    
    def on_close(self, ws, close_status_code, close_msg):
        """WebSocket connection closed"""
        self.notifier.log_info(f"WebSocket closed: {close_status_code} - {close_msg}")
        self.running = False
    
    def start_ping_thread(self):
        """Start thread to send periodic pings"""
        def send_pings():
            while self.running and self.ws:
                try:
                    time.sleep(WEBSOCKET_PING_INTERVAL)
                    if self.ws and self.running:
                        self.ws.send("ping")
                except Exception as e:
                    self.notifier.log_error(f"Error sending ping: {e}")
                    break
        
        self.ping_thread = threading.Thread(target=send_pings, daemon=True)
        self.ping_thread.start()
    
    def start_refetch_thread(self):
        """Start thread to periodically refetch and subscribe to new markets"""
        def refetch_markets():
            while self.running:
                try:
                    # Wait for refetch interval
                    time.sleep(REFETCH_INTERVAL)
                    
                    if not self.running or not self.ws:
                        break
                    
                    # Check if it's time to refetch
                    time_since_last = time.time() - self.last_refetch_time
                    if time_since_last >= REFETCH_INTERVAL:
                        self.notifier.log_info(
                            f"🔄 Refetching markets to discover new trending markets "
                            f"(last fetch: {int(time_since_last/60)} minutes ago)"
                        )
                        
                        # Resubscribe to markets (will fetch new ones)
                        self.subscribe_to_markets()
                        
                except Exception as e:
                    self.notifier.log_error(f"Error in refetch thread: {e}")
                    time.sleep(60)  # Wait a bit before retrying
        
        self.refetch_thread = threading.Thread(target=refetch_markets, daemon=True)
        self.refetch_thread.start()
        self.notifier.log_info(f"📅 Scheduled market refetch every {REFETCH_INTERVAL/3600:.1f} hours")
    
    def get_high_rate_markets(self):
        """
        Get list of active markets with rate above HIGH_RATE_THRESHOLD
        
        Returns:
            List of dicts with market info for monitor display
        """
        high_rate_markets = []
        
        for market in self.latest_markets:
            try:
                market_id = market.get('id')
                if not market_id:
                    continue
                
                # Skip filtered markets
                if self.should_filter_market(market):
                    continue
                
                # Get current price from history
                current_price = self.price_history.get(market_id)
                if current_price is None:
                    # Try to get from market data
                    if 'lastTradePrice' in market and market['lastTradePrice']:
                        current_price = float(market['lastTradePrice'])
                    else:
                        continue
                
                # Check if in threshold range (70% to 97%)
                if HIGH_RATE_THRESHOLD_MIN <= current_price < HIGH_RATE_THRESHOLD_MAX:
                    # Get outcome name
                    outcome_name = "Yes"  # default
                    if 'outcomes' in market and market['outcomes']:
                        outcomes = market['outcomes']
                        if isinstance(outcomes, str):
                            import json as json_lib
                            outcomes = json_lib.loads(outcomes)
                        if outcomes and len(outcomes) > 0:
                            outcome_name = outcomes[0]
                    
                    # Build link
                    event_slug = market.get('event_slug', '')
                    market_slug = market.get('slug', '')
                    link = f"https://polymarket.com/event/{event_slug or market_slug}"
                    
                    high_rate_markets.append({
                        'question': market.get('question', 'Unknown'),
                        'rate': current_price,
                        'outcome': outcome_name,
                        'link': link,
                        'event_title': market.get('event_title', ''),
                        'market_id': market_id
                    })
            except Exception as e:
                continue
        
        return high_rate_markets
    
    def _monitor_loop(self):
        """Background thread to update pinned monitor message"""
        self.notifier.log_info("🔥 Started pinned message monitor thread")
        
        while self.monitor_running and self.running:
            try:
                # Get high rate markets
                high_rate_markets = self.get_high_rate_markets()
                
                # Update pinned message
                self.notifier.send_or_update_monitor_message(high_rate_markets)
                
                # Wait for next update
                time.sleep(PINNED_MESSAGE_UPDATE_INTERVAL)
            except Exception as e:
                self.notifier.log_error(f"Error in monitor loop: {e}")
                time.sleep(PINNED_MESSAGE_UPDATE_INTERVAL)
    
    def start_monitor(self):
        """Start the monitor thread for pinned message"""
        if not ENABLE_PINNED_MONITOR:
            return
        
        if not self.monitor_running:
            self.monitor_running = True
            self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self.monitor_thread.start()
            self.notifier.log_info("✅ Pinned message monitor enabled")
    
    def stop_monitor(self):
        """Stop the monitor thread"""
        if self.monitor_running:
            self.monitor_running = False
            if self.monitor_thread:
                self.monitor_thread.join(timeout=5)
            self.notifier.log_info("⏹️ Pinned message monitor stopped")
    
    def run(self):
        """Start WebSocket tracker"""
        self.notifier.log_info(f"Starting WebSocket Market Tracker...")
        self.notifier.log_info(f"Category: {CATEGORY}")
        self.notifier.log_info(f"Price change threshold: {PRICE_CHANGE_THRESHOLD:.0%}")
        self.notifier.log_info(f"Max markets to track: {MAX_MARKETS_TO_SUBSCRIBE}")
        
        self.running = True
        
        # Start monitor thread for pinned message
        self.start_monitor()
        
        # Disable SSL verification for WebSocket
        import ssl
        ssl_options = {"cert_reqs": ssl.CERT_NONE}
        
        try:
            # Create WebSocket connection
            # Note: websocket-client doesn't support HTTP proxy well
            # If you need proxy, consider using SOCKS proxy or tunneling solution
            self.ws = websocket.WebSocketApp(
                WEBSOCKET_URL,
                on_open=self.on_open,
                on_message=self.on_message,
                on_error=self.on_error,
                on_close=self.on_close
            )
            
            # Run forever (blocking) with SSL options
            self.ws.run_forever(sslopt=ssl_options)
            
        except KeyboardInterrupt:
            self.notifier.log_info("Bot stopped by user")
            self.running = False
            self.stop_monitor()  # Stop monitor thread
            if self.ws:
                self.ws.close()
            self.save_price_history()
        except Exception as e:
            self.notifier.log_error(f"Fatal error: {e}")
            self.running = False
            self.stop_monitor()  # Stop monitor thread
            self.save_price_history()
