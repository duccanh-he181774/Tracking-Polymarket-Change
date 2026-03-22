# Bot Configuration Settings

# API Endpoints
GAMMA_API_URL = "https://gamma-api.polymarket.com"
CLOB_API_URL = "https://clob.polymarket.com"

# Market Tracking Settings
CATEGORY = "breaking"  # Category to monitor: "breaking", "crypto", "politics", etc.
CHECK_INTERVAL = 10  # Check every 10 seconds
PRICE_CHANGE_THRESHOLD = 0.1  # Absolute percentage point change (0.1 = 10%)
REFETCH_INTERVAL = 3600  # Refetch markets every 1 hour

# WebSocket Settings
USE_WEBSOCKET = False  # True = WebSocket real-time, False = Polling
WEBSOCKET_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
WEBSOCKET_PING_INTERVAL = 10
MAX_MARKETS_TO_SUBSCRIBE = 500

# Notification Settings
ENABLE_CONSOLE_NOTIFICATION = True

ENABLE_TELEGRAM_NOTIFICATION = False
TELEGRAM_BOT_TOKEN = ""  # Get from @BotFather on Telegram
TELEGRAM_CHAT_ID = ""  # Your chat or group ID

ENABLE_DISCORD_NOTIFICATION = False
DISCORD_WEBHOOK_URL = ""  # Discord webhook URL

# Proxy Settings
USE_PROXY = False
PROXY_URL = "http://username:password@ip:port"

# Market Filters
MIN_VOLUME = 100000  # Minimum volume to track (USD)
MAX_MARKETS_TO_TRACK = 500
USE_PARALLEL_FETCHING = True

# Data Storage
PRICE_HISTORY_FILE = "price_history.json"

# Pinned Message Monitor Settings
ENABLE_PINNED_MONITOR = False
HIGH_RATE_THRESHOLD_MIN = 0.7  # Show markets with rate >= 70%
HIGH_RATE_THRESHOLD_MAX = 0.9  # Show markets with rate < 90%
PINNED_MESSAGE_UPDATE_INTERVAL = 30  # Update every 30 seconds
PINNED_MESSAGE_ID_FILE = "pinned_message_id.txt"
