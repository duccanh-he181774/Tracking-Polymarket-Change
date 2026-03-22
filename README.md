# Polymarket Market Tracker Bot

Bot theo dõi biến động giá của các market trên Polymarket và gửi thông báo khi phát hiện thay đổi lớn.

## Tính năng

- Theo dõi các market theo category (breaking, crypto, politics, etc.)
- Hỗ trợ theo dõi đến 500 markets đồng thời
- Fast polling mode - kiểm tra mỗi 10 giây
- Phát hiện biến động giá >= ngưỡng cấu hình (mặc định 10%)
- Thông báo qua Console, Telegram, Discord
- Lưu lịch sử giá để theo dõi liên tục
- Hỗ trợ proxy (HTTP/HTTPS)
- Lọc theo volume tối thiểu
- Pinned message monitor - ghim tin nhắn high-rate markets trên Telegram
- Chế độ WebSocket (real-time) và Polling

## Cấu trúc file

```
bot.py                 # Điểm khởi chạy bot
config.py              # Cấu hình (API, Telegram, proxy, etc.)
market_tracker.py      # Polling tracker - kiểm tra giá theo interval
websocket_tracker.py   # WebSocket tracker - nhận giá real-time
notifier.py            # Gửi thông báo (Console, Telegram, Discord)
generate_api_key.py    # Tạo API key cho Polymarket CLOB
```

## Hướng dẫn cài đặt

### 1. Cài đặt Python

Cần Python 3.10+. Tải từ https://www.python.org/downloads/

### 2. Tạo virtual environment (khuyến nghị)

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux/Mac
source .venv/bin/activate
```

### 3. Cài đặt thư viện

```bash
pip install -r requirements.txt
```

### 4. Cấu hình

Sao chép file mẫu và chỉnh sửa:

```bash
cp config.sample.py config.py
```

Mở file `config.py` và chỉnh sửa:

#### API & Market
```python
CATEGORY = "breaking"           # Category cần theo dõi
CHECK_INTERVAL = 10             # Kiểm tra mỗi 10 giây
PRICE_CHANGE_THRESHOLD = 0.1    # Ngưỡng 10% (0.1 = 10 percentage points)
MIN_VOLUME = 100000             # Volume tối thiểu (USD)
MAX_MARKETS_TO_TRACK = 500      # Tối đa 500 markets
```

#### Telegram (tuỳ chọn)
```python
ENABLE_TELEGRAM_NOTIFICATION = True
TELEGRAM_BOT_TOKEN = "your_bot_token"
TELEGRAM_CHAT_ID = "your_chat_id"
```

Để tạo Telegram bot:
1. Chat với @BotFather trên Telegram
2. Gửi `/newbot` và làm theo hướng dẫn để lấy token
3. Thêm bot vào group hoặc chat trực tiếp với bot
4. Lấy chat_id từ: `https://api.telegram.org/bot<TOKEN>/getUpdates`

#### Discord (tuỳ chọn)
```python
ENABLE_DISCORD_NOTIFICATION = True
DISCORD_WEBHOOK_URL = "your_webhook_url"
```

#### Proxy (nếu cần)
```python
USE_PROXY = True
PROXY_URL = "http://username:password@ip:port"
```

#### Pinned Message Monitor
```python
ENABLE_PINNED_MONITOR = True        # Bật/tắt pinned message
HIGH_RATE_THRESHOLD_MIN = 0.7       # Hiển thị market >= 70%
HIGH_RATE_THRESHOLD_MAX = 0.9       # Hiển thị market < 90%
PINNED_MESSAGE_UPDATE_INTERVAL = 30 # Cập nhật mỗi 30 giây
```

#### Chế độ WebSocket
```python
USE_WEBSOCKET = False   # True = WebSocket real-time, False = Polling
```

### 5. Chạy bot

```bash
python bot.py
```

Nhấn `Ctrl+C` để dừng bot.

## Ví dụ thông báo

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

## Các category phổ biến

- `breaking` - Tin nóng
- `crypto` - Tiền mã hoá
- `politics` - Chính trị
- `sports` - Thể thao
- `business` - Kinh doanh
- `science` - Khoa học
- `pop-culture` - Văn hoá

## Xử lý sự cố

**Bot không kết nối được:**
- Kiểm tra proxy có hoạt động không
- Kiểm tra kết nối internet
- Thử tắt proxy (`USE_PROXY = False`)

**Không nhận được thông báo:**
- Kiểm tra `ENABLE_TELEGRAM_NOTIFICATION = True`
- Kiểm tra ngưỡng có phù hợp không (giảm `PRICE_CHANGE_THRESHOLD`)
- Kiểm tra `MIN_VOLUME` có quá cao không

**Quá nhiều thông báo:**
- Tăng `PRICE_CHANGE_THRESHOLD` (ví dụ: 0.3 = 30%)
- Tăng `CHECK_INTERVAL` (ví dụ: 60 giây)
- Tăng `MIN_VOLUME` để lọc market nhỏ
