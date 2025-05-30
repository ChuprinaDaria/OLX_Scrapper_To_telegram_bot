# 🔍 OLX Ads Monitoring Telegram Bot

<div align="center">
  <img src="photo_2025-05-30_09-20-37.jpg" alt="OLX Bot Logo" width="200"/>
  
  **A Python-based Telegram bot that automatically monitors free ads on OLX and sends the freshest ads to specified Telegram chats.**
  
  [![Python](https://img.shields.io/badge/Python-3.7+-blue.svg)](https://www.python.org/)
  [![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
  [![Telegram](https://img.shields.io/badge/Telegram-Bot-blue.svg)](https://telegram.org/)
</div>

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 📡 **Real-time Monitoring** | Monitors new listings on OLX and OTOMOTO in real-time, only sending the freshest ads |
| 📤 **Auto-posting** | Automatically posts to Telegram chats with clean Markdown formatting and optional images |
| 🛠️ **Admin Panel** | Built-in Telegram admin panel to manage monitored URLs (add/list/delete) |
| ⚙️ **Easy Configuration** | Simple `.env` file configuration for tokens, IDs, and file paths |
| 🚀 **High Performance** | Powered by DrissionPage for fast, stealthy scraping without Selenium overhead |
| 🔁 **Parallel Processing** | Checks multiple URLs in parallel for optimal performance |
| 🧠 **Smart Intervals** | Dynamically adjusts checking intervals based on new ad detection |
| 💾 **Persistent Storage** | SQLite database with deduplication and automatic cleanup |
| 👥 **Multi-chat Support** | Supports multiple Telegram chat IDs for broad distribution |
| 🔐 **Admin Control** | Admin-only access for managing bot behavior and database |

---

## 🚀 Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/ChuprinaDaria/OLX_Scrapper_To_telegram_bot.git
cd OLX_Scrapper_To_telegram_bot
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Create a `.env` file in the root directory:

```env
# Telegram Configuration
TELEGRAM_TOKEN=your_bot_token_here
CHAT_IDS=-1000000000,-1001000000
ADMIN_IDS=1234567890,0987654321

# Database and Files
DB_FILE=olx_ads.db
URLS_FILE=tracked_urls.json
```

> **Getting Your Tokens:**
> - `TELEGRAM_TOKEN`: Get from [@BotFather](https://t.me/botfather) on Telegram
> - `CHAT_IDS`: Get chat IDs from [@userinfobot](https://t.me/userinfobot)
> - `ADMIN_IDS`: Your Telegram user ID (also from [@userinfobot](https://t.me/userinfobot))

### 4. Run the Bot

```bash
python bot.py
```

🎉 **That's it!** The bot will start monitoring and sending fresh ads to your specified channels.

---

## ⚙️ Configuration & Customization

### Scanning Parameters

Fine-tune the bot's behavior by editing these constants in `OLX.py`:

```python
# Timing Configuration
QUICK_CHECK_INTERVAL = 15      # Seconds between quick scans
MIN_INTERVAL = 20              # Minimum wait time after scan
MAX_INTERVAL = 40              # Maximum wait time if nothing found

# Ad Filtering
MAX_AD_AGE_MINUTES = 50        # Only process ads newer than this
VERY_FRESH_AD_MINUTES = 10     # Mark ads as "🔥 VERY FRESH"

# Parsing Settings
SKIP_FIRST_N_ADS = 2           # Skip promoted/sponsored ads
MAX_CARDS_TO_CHECK = 13        # Listings to process per scan
SCROLL_COUNT = 4               # Page scroll depth

# Performance
MAX_PARALLEL_URLS = 3          # Concurrent URL scanning
PAGE_LOAD_TIMEOUT = 40         # Page load wait time (seconds)

# Optimization
CONSECUTIVE_OLD_COUNT = 3      # Stop if N old ads found in row
EARLY_EXIT_ON_OLD = True       # Enable early exit optimization
DETAILED_LOGGING = True        # Verbose logging for debugging
```

---

## 📱 Admin Commands

Use these commands in Telegram to manage your bot:

| Command | Description |
|---------|-------------|
| `/add_url <URL>` | Add a new OLX/OTOMOTO URL to monitor |
| `/list_urls` | Show all currently monitored URLs |
| `/delete_url <index>` | Remove a URL from monitoring |
| `/stats` | Show bot statistics and database info |

---

## 📋 Example Output

Here's how ads appear in your Telegram chat:

```
📌 oddam za darmo skrzynie ze sklejki palety CID628
⏱️ 46.8 min ago | 🔥 VERY FRESH
📆 23 maja 2025
💰 Free
📍 Kraków, Małopolskie
🔗 [View Ad](https://www.olx.pl/example-ad)
```

---

## 🛠️ Tech Stack

- **Python 3.7+** - Core language
- **[DrissionPage](https://github.com/michiya/DrissionPage)** - Web scraping without Selenium
- **SQLite** - Local database for ad storage
- **python-telegram-bot** - Telegram API wrapper
- **asyncio** - Asynchronous processing

---

## 📊 Performance

- **Parallel Processing**: Monitors up to 3 URLs simultaneously
- **Smart Caching**: Prevents duplicate ad notifications
- **Optimized Scanning**: Early exit when old ads are detected
- **Memory Efficient**: Automatic cleanup of expired ad data

---

## 🤝 Contributing

We welcome contributions! Here's how you can help:

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Commit** your changes (`git commit -m 'Add amazing feature'`)
4. **Push** to the branch (`git push origin feature/amazing-feature`)
5. **Open** a Pull Request

### Issues & Feature Requests

- 🐛 **Bug reports**: [Create an issue](../../issues)
- 💡 **Feature requests**: [Create an issue](../../issues)
- 💬 **Questions**: [Discussions](../../discussions)

---

## ⚠️ Disclaimer

> **Educational Purpose**: This project was created for personal use and educational purposes (originally for searching for a free refrigerator 😄). Please use responsibly and respect OLX's terms of service.

---

## 📄 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

---

<div align="center">
  
**Made with ❤️ for the community**

If this project helped you, consider giving it a ⭐!

</div>
