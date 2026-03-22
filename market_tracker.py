import requests
import json
import time
import threading
from datetime import datetime
from typing import Dict, List, Optional
from notifier import Notifier
from config import (
    GAMMA_API_URL,
    CATEGORY,
    CHECK_INTERVAL,
    PRICE_CHANGE_THRESHOLD,
    MIN_VOLUME,
    MAX_MARKETS_TO_TRACK,
    PRICE_HISTORY_FILE,
    USE_PROXY,
    PROXY_URL,
    USE_PARALLEL_FETCHING,
    ENABLE_PINNED_MONITOR,
    HIGH_RATE_THRESHOLD_MIN,
    HIGH_RATE_THRESHOLD_MAX,
    PINNED_MESSAGE_UPDATE_INTERVAL
)

class MarketTracker:
    """Tracks Polymarket markets and detects price movements"""
    
    def __init__(self):
        self.notifier = Notifier()
        self.price_history: Dict[str, float] = {}  # Last known prices
        self.baseline_prices: Dict[str, float] = {}  # Baseline for cumulative change detection
        self.market_info: Dict[str, dict] = {}
        self.proxies = {"http": PROXY_URL, "https": PROXY_URL} if USE_PROXY else None
        self.session = requests.Session()
        if USE_PROXY:
            self.session.proxies.update(self.proxies)
        self.load_price_history()
        
        # Monitor thread for pinned message
        self.monitor_running = False
        self.monitor_thread = None
        self.latest_markets = []  # Store latest markets for monitor
    
    def load_price_history(self):
        """Load previous price history from file"""
        try:
            with open(PRICE_HISTORY_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.price_history = data.get('price_history', {})
                self.baseline_prices = data.get('baseline_prices', {})
                self.market_info = data.get('market_info', {})
            self.notifier.log_info(f"Loaded {len(self.price_history)} markets from history")
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
                    self.baseline_prices.pop(market_id, None)
                    self.market_info.pop(market_id, None)
                
                self.notifier.log_info(f"🧹 Cleaned up {len(closed_ids)} closed markets from history")
                # Save after cleanup
                self.save_price_history()
        except Exception as e:
            self.notifier.log_error(f"Error cleaning up closed markets: {e}")
    
    def save_price_history(self):
        """Save current price history to file"""
        try:
            data = {
                'price_history': self.price_history,
                'baseline_prices': self.baseline_prices,
                'market_info': self.market_info,
                'last_updated': datetime.now().isoformat()
            }
            with open(PRICE_HISTORY_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.notifier.log_error(f"Error saving price history: {e}")
    
    def get_markets_by_category(self, category: str, limit: int = 100) -> List[dict]:
        """
        Fetch markets from Gamma API by category using Events endpoint
        
        Args:
            category: Category tag to filter by
            limit: Maximum number of events to fetch
            
        Returns:
            List of market dictionaries
        """
        try:
            # Use Events endpoint for better, more current results
            url = f"{GAMMA_API_URL}/events"
            params = {
                "tag": category,
                "limit": limit,
                "closed": "false",
                "order": "volume24hr",
                "ascending": "false"
            }
            
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            events = response.json()
            
            # Extract all markets from events
            markets = []
            for event in events:
                event_markets = event.get('markets', [])
                # Get event tags for filtering
                event_tags = event.get('tags', [])
                # Add event info to each market for better context
                for market in event_markets:
                    market['event_title'] = event.get('title', '')
                    market['event_slug'] = event.get('slug', '')
                    market['event_tags'] = event_tags  # Add tags for filtering
                    # Use event volume if market volume not available
                    if not market.get('volume'):
                        market['volume'] = event.get('volume', 0)
                    markets.append(market)
            
            # Reduced logging - only log occasionally
            # self.notifier.log_info(f"Fetched {len(events)} events with {len(markets)} total markets from '{category}'")
            return markets
            
        except requests.exceptions.RequestException as e:
            self.notifier.log_error(f"Error fetching markets: {e}")
            return []
    
    def get_market_price(self, market: dict) -> tuple[Optional[float], Optional[str]]:
        """
        Extract current price and outcome name from market data
        
        Args:
            market: Market dictionary from API
            
        Returns:
            Tuple of (price, outcome_name) or (None, None)
        """
        try:
            import json
            
            # Get outcome name (usually "Yes" is the first outcome)
            outcome_name = "Yes"  # default
            if 'outcomes' in market and market['outcomes']:
                outcomes_str = market['outcomes']
                if isinstance(outcomes_str, str):
                    outcomes = json.loads(outcomes_str)
                    if outcomes and len(outcomes) > 0:
                        outcome_name = outcomes[0]
                elif isinstance(outcomes_str, list):
                    outcome_name = outcomes_str[0]
            
            # Method 1: Use lastTradePrice (most reliable and current)
            if 'lastTradePrice' in market and market['lastTradePrice']:
                return float(market['lastTradePrice']), outcome_name
            
            # Method 2: Use best bid/ask mid price
            if 'bestBid' in market and 'bestAsk' in market:
                best_bid = market.get('bestBid')
                best_ask = market.get('bestAsk')
                if best_bid and best_ask:
                    return (float(best_bid) + float(best_ask)) / 2, outcome_name
            
            # Method 3: Parse outcomePrices (it's a JSON string)
            if 'outcomePrices' in market and market['outcomePrices']:
                outcome_prices_str = market['outcomePrices']
                if isinstance(outcome_prices_str, str):
                    prices = json.loads(outcome_prices_str)
                    if prices and len(prices) > 0:
                        return float(prices[0]), outcome_name
                elif isinstance(outcome_prices_str, list):
                    return float(outcome_prices_str[0]), outcome_name
            
            # Method 4: Try tokens field
            if 'tokens' in market and market['tokens']:
                token = market['tokens'][0]
                if 'price' in token and token['price']:
                    return float(token['price']), outcome_name
            
            return None, None
            
        except (KeyError, ValueError, IndexError, json.JSONDecodeError) as e:
            # Don't log every error to avoid spam
            return None, None
    
    def check_price_changes(self, markets: List[dict]):
        """
        Check for significant price changes in markets
        
        Args:
            markets: List of market dictionaries
        """
        alerts_sent = 0
        markets_checked = 0
        new_markets_found = 0
        filtered_count = 0
        active_market_ids = set()
        
        # Store latest markets for monitor
        self.latest_markets = markets
        
        for market in markets[:MAX_MARKETS_TO_TRACK]:
            try:
                market_id = market.get('id')
                if not market_id:
                    continue
                
                # Track active market IDs for cleanup
                active_market_ids.add(market_id)
                
                # Filter out Bitcoin price predictions and sports
                if self.should_filter_market(market):
                    filtered_count += 1
                    continue
                
                # Get current price and outcome name
                current_price, outcome_name = self.get_market_price(market)
                if current_price is None:
                    continue
                
                # Get volume (if available)
                volume = float(market.get('volume', 0))
                
                # Skip low volume markets
                if volume < MIN_VOLUME:
                    continue
                
                markets_checked += 1
                
                # Initialize baseline if this is first time seeing this market
                is_new_market = market_id not in self.baseline_prices
                if is_new_market:
                    self.baseline_prices[market_id] = current_price
                    new_markets_found += 1
                
                # Get baseline price for cumulative change detection
                baseline_price = self.baseline_prices[market_id]
                
                # Calculate absolute price change (percentage points)
                # Example: 0.01 (1%) to 0.11 (11%) = 0.10 change (10 percentage points)
                price_change = current_price - baseline_price
                
                # Check if absolute change exceeds threshold
                if abs(price_change) >= PRICE_CHANGE_THRESHOLD:
                        direction = "UP" if price_change > 0 else "DOWN"
                        
                        # Prepare market data for notification
                        market_data = {
                            'question': market.get('question', 'Unknown'),
                            'event_title': market.get('event_title', ''),
                            'event_slug': market.get('event_slug', ''),
                            'outcome': outcome_name,
                            'current_price': current_price,
                            'previous_price': baseline_price,  # Show baseline as "previous"
                            'volume': volume,
                            'slug': market.get('slug', ''),
                            'id': market_id
                        }
                        
                        # Send alert
                        self.notifier.send_alert(market_data, price_change, direction)
                        alerts_sent += 1
                        
                        # Reset baseline after alerting
                        self.baseline_prices[market_id] = current_price
                
                # Always update current price history
                self.price_history[market_id] = current_price
                
                # Store market info for reference
                self.market_info[market_id] = {
                    'question': market.get('question', 'Unknown'),
                    'event_title': market.get('event_title', ''),
                    'event_slug': market.get('event_slug', ''),
                    'slug': market.get('slug', ''),
                    'volume': volume
                }
                
            except Exception as e:
                self.notifier.log_error(f"Error processing market {market.get('id', 'unknown')}: {e}")
                continue
        
        # Cleanup closed markets periodically
        self.cleanup_closed_markets(active_market_ids)
        
        # Log when alerts are sent or new markets found
        if alerts_sent > 0 or new_markets_found > 0 or filtered_count > 0:
            log_parts = []
            log_parts.append(f"Checked {markets_checked} markets")
            if filtered_count > 0:
                log_parts.append(f"🚫 Filtered {filtered_count} (Bitcoin/Sports)")
            if alerts_sent > 0:
                log_parts.append(f"{alerts_sent} alerts")
            if new_markets_found > 0:
                log_parts.append(f"🆕 {new_markets_found} new markets discovered")
            self.notifier.log_info(" | ".join(log_parts))
    
    def get_high_rate_markets(self) -> List[dict]:
        """
        Get list of active markets with rate above HIGH_RATE_THRESHOLD
        
        Returns:
            List of dicts with market info for monitor display
        """
        high_rate_markets = []
        
        for market in self.latest_markets:
            try:
                # Skip filtered markets
                if self.should_filter_market(market):
                    continue
                
                # Get current price
                current_price, outcome_name = self.get_market_price(market)
                if current_price is None:
                    continue
                
                # Check if in threshold range (70% to 97%)
                if HIGH_RATE_THRESHOLD_MIN <= current_price < HIGH_RATE_THRESHOLD_MAX:
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
                        'market_id': market.get('id', '')
                    })
            except Exception as e:
                continue
        
        return high_rate_markets
    
    def _monitor_loop(self):
        """Background thread to update pinned monitor message"""
        self.notifier.log_info("🔥 Started pinned message monitor thread")
        
        while self.monitor_running:
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
        """Main bot loop to continuously monitor markets"""
        self.notifier.log_info(f"Starting Market Tracker Bot...")
        self.notifier.log_info(f"Category: {CATEGORY}")
        self.notifier.log_info(f"Check interval: {CHECK_INTERVAL}s")
        self.notifier.log_info(f"Price change threshold: {PRICE_CHANGE_THRESHOLD:.0%}")
        self.notifier.log_info(f"Max markets to track: {MAX_MARKETS_TO_TRACK}")
        self.notifier.log_info(f"Min volume filter: ${MIN_VOLUME:,.0f}")
        
        # Start monitor thread for pinned message
        self.start_monitor()
        
        iteration = 0
        try:
            while True:
                try:
                    iteration += 1
                    start_time = time.time()
                    
                    # Fetch markets
                    markets = self.get_markets_by_category(CATEGORY, limit=200)
                    
                    if markets:
                        # Check for price changes
                        self.check_price_changes(markets)
                        
                        # Save price history periodically (every 10 iterations)
                        if iteration % 10 == 0:
                            self.save_price_history()
                            self.notifier.log_info(
                                f"Tracking {len(self.price_history)} markets | "
                                f"Iteration {iteration}"
                            )
                        
                        elapsed = time.time() - start_time
                        # Reduced logging
                        # self.notifier.log_info(
                        #     f"Cycle completed in {elapsed:.2f}s | "
                        #     f"Next check in {CHECK_INTERVAL}s"
                        # )
                    else:
                        self.notifier.log_info("No markets found, will retry...")
                    
                    # Wait before next check
                    time.sleep(CHECK_INTERVAL)
                    
                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    self.notifier.log_error(f"Error in main loop: {e}")
                    time.sleep(CHECK_INTERVAL)
                    
        except KeyboardInterrupt:
            self.notifier.log_info("Bot stopped by user")
            self.stop_monitor()  # Stop monitor thread
            self.save_price_history()
            self.notifier.log_info(
                f"Final statistics: {len(self.price_history)} markets tracked"
            )
        except Exception as e:
            self.notifier.log_error(f"Fatal error: {e}")
            self.stop_monitor()  # Stop monitor thread
            self.save_price_history()
