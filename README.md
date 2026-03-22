# Polymarket Market Tracker Bot

Bot theo doi bien dong gia cua cac market tren Polymarket va gui thong bao khi phat hien thay doi lon.

## Tinh nang

- Theo doi cac market theo category (breaking, crypto, politics, etc.)
- Ho tro theo doi den 500 markets dong thoi
- Fast polling mode - kiem tra moi 10 giay
- Phat hien bien dong gia >= nguong cau hinh (mac dinh 10%)
- Thong bao qua Console, Telegram, Discord
- Luu lich su gia de theo doi lien tuc
- Ho tro proxy (HTTP/HTTPS)
- Loc theo volume toi thieu
- Pinned message monitor - ghim tin nhan high-rate markets tren Telegram
- Che do WebSocket (real-time) va Polling

## Cau truc file

```
bot.py                 # Entry point - chay bot
config.py              # Cau hinh (API, Telegram, proxy, etc.)
market_tracker.py      # Polling tracker - kiem tra gia theo interval
websocket_tracker.py   # WebSocket tracker - nhan gia real-time
notifier.py            # Gui thong bao (Console, Telegram, Discord)
generate_api_key.py    # Tao API key cho Polymarket CLOB
```

## Setup

### 1. Cai dat Python

Can Python 3.10+ . Tai tu https://www.python.org/downloads/

### 2. Tao virtual environment (khuyen nghi)

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux/Mac
source .venv/bin/activate
```

### 3. Cai dat thu vien

```bash
pip install requests websocket-client
```

### 4. Cau hinh

Mo file `config.py` va chinh sua:

#### API & Market
```python
CATEGORY = "breaking"           # Category can theo doi
CHECK_INTERVAL = 10             # Kiem tra moi 10 giay
PRICE_CHANGE_THRESHOLD = 0.1    # Nguong 10% (0.1 = 10 percentage points)
MIN_VOLUME = 100000             # Volume toi thieu (USD)
MAX_MARKETS_TO_TRACK = 500      # Toi da 500 markets
```

#### Telegram (tuy chon)
```python
ENABLE_TELEGRAM_NOTIFICATION = True
TELEGRAM_BOT_TOKEN = "your_bot_token"
TELEGRAM_CHAT_ID = "your_chat_id"
```

De tao Telegram bot:
1. Chat voi @BotFather tren Telegram
2. Gui `/newbot` va lam theo huong dan de lay token
3. Them bot vao group hoac chat truc tiep voi bot
4. Lay chat_id tu: `https://api.telegram.org/bot<TOKEN>/getUpdates`

#### Discord (tuy chon)
```python
ENABLE_DISCORD_NOTIFICATION = True
DISCORD_WEBHOOK_URL = "your_webhook_url"
```

#### Proxy (neu can)
```python
USE_PROXY = True
PROXY_URL = "http://username:password@ip:port"
```

#### Pinned Message Monitor
```python
ENABLE_PINNED_MONITOR = True        # Bat/tat pinned message
HIGH_RATE_THRESHOLD_MIN = 0.7       # Hien thi market >= 70%
HIGH_RATE_THRESHOLD_MAX = 0.9       # Hien thi market < 90%
PINNED_MESSAGE_UPDATE_INTERVAL = 30 # Cap nhat moi 30 giay
```

#### Che do WebSocket
```python
USE_WEBSOCKET = False   # True = WebSocket real-time, False = Polling
```

### 5. Chay bot

```bash
python bot.py
```

Nhan `Ctrl+C` de dung bot.

## Vi du thong bao

```
📈 POLYMARKET ALERT 📈

Event: Bitcoin 100k
Market: Will Bitcoin hit $100k in March 2026?
Outcome: "Yes" ↑ 25.3%
Current Price: 75.3%
Previous Price: 50.0%
Volume: $125,432
Link: https://polymarket.com/event/bitcoin-100k-march-2026

Time: 2026-03-02 14:30:45
```

## Cac category pho bien

- `breaking` - Tin nong
- `crypto` - Cryptocurrency
- `politics` - Chinh tri
- `sports` - The thao
- `business` - Kinh doanh
- `science` - Khoa hoc
- `pop-culture` - Van hoa

## Troubleshooting

**Bot khong ket noi duoc:**
- Kiem tra proxy co hoat dong khong
- Kiem tra ket noi internet
- Thu tat proxy (`USE_PROXY = False`)

**Khong nhan duoc thong bao:**
- Kiem tra `ENABLE_TELEGRAM_NOTIFICATION = True`
- Kiem tra threshold co phu hop khong (giam `PRICE_CHANGE_THRESHOLD`)
- Kiem tra `MIN_VOLUME` co qua cao khong

**Qua nhieu thong bao:**
- Tang `PRICE_CHANGE_THRESHOLD` (vi du: 0.3 = 30%)
- Tang `CHECK_INTERVAL` (vi du: 60 giay)
- Tang `MIN_VOLUME` de loc market nho
