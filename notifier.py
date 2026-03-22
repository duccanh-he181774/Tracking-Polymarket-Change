import requests
from datetime import datetime
from config import (
    ENABLE_CONSOLE_NOTIFICATION,
    ENABLE_TELEGRAM_NOTIFICATION,
    ENABLE_DISCORD_NOTIFICATION,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    DISCORD_WEBHOOK_URL,
    USE_PROXY,
    PROXY_URL,
    ENABLE_PINNED_MONITOR,
    PINNED_MESSAGE_ID_FILE
)

class Notifier:
    """Handles notifications for market alerts"""
    
    def __init__(self):
        self.proxies = {"http": PROXY_URL, "https": PROXY_URL} if USE_PROXY else None
        self.pinned_message_id = None
        if ENABLE_PINNED_MONITOR:
            self._load_pinned_message_id()
    
    def send_alert(self, market_data, price_change, direction):
        """
        Send alert through configured channels
        
        Args:
            market_data: Market information dict
            price_change: Absolute percentage point change (e.g., 0.10 for 10 percentage points)
            direction: "UP" or "DOWN"
        """
        message = self._format_message(market_data, price_change, direction)
        
        # Console notification
        if ENABLE_CONSOLE_NOTIFICATION:
            self._send_console(message, direction)
        
        # Telegram notification
        if ENABLE_TELEGRAM_NOTIFICATION and TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
            self._send_telegram(message)
        
        # Discord notification
        if ENABLE_DISCORD_NOTIFICATION and DISCORD_WEBHOOK_URL:
            self._send_discord(message, direction)
        
        # Don't log to file to save disk space
        # logging.info(message)
    
    def _format_message(self, market_data, price_change, direction):
        """Format alert message"""
        emoji = "📈" if direction == "UP" else "📉"
        arrow = "↑" if direction == "UP" else "↓"
        
        # Build link - try event_slug first, fallback to market slug
        event_slug = market_data.get('event_slug', '')
        market_slug = market_data.get('slug', '')
        link = f"https://polymarket.com/event/{event_slug or market_slug}"
        
        # Format event context if available
        event_context = ""
        if market_data.get('event_title'):
            event_context = f"Event: {market_data['event_title']}\n"
        
        # Get outcome (Yes/No)
        outcome = market_data.get('outcome', 'Yes')
        
        # Convert prices to percentages
        current_price_pct = market_data['current_price'] * 100
        previous_price_pct = market_data['previous_price'] * 100
        
        message = f"""
{emoji} POLYMARKET ALERT {emoji}

{event_context}Market: {market_data['question']}
Outcome: "{outcome}" {arrow} {abs(price_change)*100:.1f}%
Current Price: {current_price_pct:.1f}%
Previous Price: {previous_price_pct:.1f}%
Volume: ${market_data.get('volume', 'N/A'):,.0f}
Link: {link}

Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
""".strip()
        
        return message
    
    def _send_console(self, message, direction):
        """Print alert to console with colors"""
        color_code = "\033[92m" if direction == "UP" else "\033[91m"  # Green for UP, Red for DOWN
        reset_code = "\033[0m"
        separator = "=" * 60
        
        print(f"\n{color_code}{separator}")
        print(message)
        print(f"{separator}{reset_code}\n")
    
    def _send_telegram(self, message):
        """Send alert via Telegram bot"""
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            data = {
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "HTML",
                "disable_web_page_preview": False
            }
            response = requests.post(url, json=data, proxies=self.proxies, timeout=10)
            if response.status_code != 200:
                print(f"ERROR: Telegram notification failed: {response.text}")
        except Exception as e:
            print(f"ERROR: Telegram notification error: {e}")
    
    def _send_discord(self, message, direction):
        """Send alert via Discord webhook"""
        try:
            color = 0x00ff00 if direction == "UP" else 0xff0000  # Green for UP, Red for DOWN
            
            embed = {
                "embeds": [{
                    "title": f"{'📈' if direction == 'UP' else '📉'} Polymarket Alert",
                    "description": message,
                    "color": color,
                    "timestamp": datetime.utcnow().isoformat()
                }]
            }
            
            response = requests.post(
                DISCORD_WEBHOOK_URL,
                json=embed,
                proxies=self.proxies,
                timeout=10
            )
            if response.status_code not in [200, 204]:
                print(f"ERROR: Discord notification failed: {response.text}")
        except Exception as e:
            print(f"ERROR: Discord notification error: {e}")
    
    def log_info(self, message):
        """Log informational message"""
        print(f"INFO: {message}")
    
    def log_error(self, message):
        """Log error message"""
        print(f"ERROR: {message}")
    
    # ==================== Pinned Message Monitor Methods ====================
    
    def _load_pinned_message_id(self):
        """Load saved pinned message ID from file"""
        try:
            with open(PINNED_MESSAGE_ID_FILE, 'r') as f:
                self.pinned_message_id = f.read().strip()
                if self.pinned_message_id:
                    self.log_info(f"Loaded pinned message ID: {self.pinned_message_id}")
        except FileNotFoundError:
            self.log_info("No previous pinned message ID found")
        except Exception as e:
            self.log_error(f"Error loading pinned message ID: {e}")
    
    def _save_pinned_message_id(self):
        """Save pinned message ID to file"""
        try:
            with open(PINNED_MESSAGE_ID_FILE, 'w') as f:
                f.write(str(self.pinned_message_id))
        except Exception as e:
            self.log_error(f"Error saving pinned message ID: {e}")
    
    def edit_telegram_message(self, message_id, text):
        """Edit an existing Telegram message"""
        if not ENABLE_TELEGRAM_NOTIFICATION or not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
            return False
        
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/editMessageText"
            data = {
                "chat_id": TELEGRAM_CHAT_ID,
                "message_id": message_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            }
            response = requests.post(url, json=data, proxies=self.proxies, timeout=10)
            
            if response.status_code == 200:
                return True
            else:
                # If message not found or too old, reset pinned message ID
                if "message to edit not found" in response.text.lower() or "message_id_invalid" in response.text.lower():
                    self.log_info("Pinned message no longer exists, will create new one")
                    self.pinned_message_id = None
                    self._save_pinned_message_id()
                else:
                    self.log_error(f"Failed to edit Telegram message: {response.text}")
                return False
        except Exception as e:
            self.log_error(f"Error editing Telegram message: {e}")
            return False
    
    def send_telegram_message(self, text):
        """Send a new Telegram message and return message ID"""
        if not ENABLE_TELEGRAM_NOTIFICATION or not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
            return None
        
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            data = {
                "chat_id": TELEGRAM_CHAT_ID,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            }
            response = requests.post(url, json=data, proxies=self.proxies, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                message_id = result.get('result', {}).get('message_id')
                return message_id
            else:
                self.log_error(f"Failed to send Telegram message: {response.text}")
                return None
        except Exception as e:
            self.log_error(f"Error sending Telegram message: {e}")
            return None
    
    def pin_telegram_message(self, message_id):
        """Pin a Telegram message"""
        if not ENABLE_TELEGRAM_NOTIFICATION or not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
            return False
        
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/pinChatMessage"
            data = {
                "chat_id": TELEGRAM_CHAT_ID,
                "message_id": message_id,
                "disable_notification": True  # Don't send notification when pinning
            }
            response = requests.post(url, json=data, proxies=self.proxies, timeout=10)
            
            if response.status_code == 200:
                self.log_info(f"Successfully pinned message {message_id}")
                return True
            else:
                self.log_error(f"Failed to pin Telegram message: {response.text}")
                return False
        except Exception as e:
            self.log_error(f"Error pinning Telegram message: {e}")
            return False
    
    def send_or_update_monitor_message(self, markets_data):
        """
        Send or update the pinned monitor message showing high-rate markets
        
        Args:
            markets_data: List of dicts with market info (question, rate, link, etc.)
        """
        if not ENABLE_PINNED_MONITOR or not ENABLE_TELEGRAM_NOTIFICATION:
            return
        
        # Format the monitor message
        message = self._format_monitor_message(markets_data)
        
        # If no pinned message exists, create new one and pin it
        if not self.pinned_message_id:
            message_id = self.send_telegram_message(message)
            if message_id:
                self.pinned_message_id = message_id
                self._save_pinned_message_id()
                self.pin_telegram_message(message_id)
                self.log_info(f"Created new pinned monitor message: {message_id}")
        else:
            # Edit existing pinned message
            success = self.edit_telegram_message(self.pinned_message_id, message)
            if not success and not self.pinned_message_id:
                # If edit failed and message was reset, create new one
                message_id = self.send_telegram_message(message)
                if message_id:
                    self.pinned_message_id = message_id
                    self._save_pinned_message_id()
                    self.pin_telegram_message(message_id)
                    self.log_info(f"Created new pinned monitor message: {message_id}")
    
    def _format_monitor_message(self, markets_data):
        """Format the monitor message with high-rate markets"""
        if not markets_data:
            return """
🔥 <b>HIGH RATE MARKETS MONITOR</b> 🔥

No markets currently in range 70% - 97%

⏰ Last updated: {}
""".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')).strip()
        
        # Sort by rate descending
        markets_data = sorted(markets_data, key=lambda x: x.get('rate', 0), reverse=True)
        
        # Build message
        lines = ["🔥 <b>HIGH RATE MARKETS MONITOR</b> 🔥\n"]
        lines.append(f"📊 <b>{len(markets_data)} market(s) in range 70% - 97%</b>\n")
        
        for idx, market in enumerate(markets_data[:20], 1):  # Limit to 20 markets to avoid message too long
            rate_pct = market['rate'] * 100
            question = market['question']
            link = market['link']
            outcome = market.get('outcome', 'Yes')
            
            # Truncate question if too long
            if len(question) > 60:
                question = question[:57] + "..."
            
            # Format: 1. Question (85.5%) - Outcome
            lines.append(f"{idx}. <a href=\"{link}\">{question}</a>")
            lines.append(f"   📈 {outcome}: <b>{rate_pct:.1f}%</b>\n")
        
        if len(markets_data) > 20:
            lines.append(f"\n... and {len(markets_data) - 20} more markets")
        
        lines.append(f"\n⏰ Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        return "\n".join(lines)
