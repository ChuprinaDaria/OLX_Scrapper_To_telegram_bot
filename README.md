# OLX Ads Monitoring Telegram Bot
![OLX](photo_2025-05-30_09-20-37.jpg)

A Python-based Telegram bot that automatically monitors free ads on OLX and sends the freshest ads to specified Telegram chats. 

## 🚀 Features

📡 Monitors new listings on OLX and OTOMOTO in real time, only sending the freshest ads
- 📡 **Real-time monitoring** of new listings on OLX and OTOMOTO — only the freshest ads are processed
- 📤 **Auto-posting to Telegram chats**, with or without images, using clean Markdown formatting
- 🛠️ **Admin panel built into Telegram** — manage monitored URLs directly from chat (add / list / delete)
- ⚙️ **Easy configuration via `.env` file** — keep tokens, IDs, and file paths clean and secure
- 🚀 **Powered by DrissionPage** — fast, stealthy scraping without the weight of Selenium
- 🔁 **Parallel URL checking** for high performance with minimal delays
- 🧠 **Smart interval handling** — rechecks sooner when new ads are detected
- 💾 **Persistent storage via SQLite**, with deduplication and automatic cleanup of expired ads
- 👥 **Supports multiple Telegram chat IDs** for broad distribution
- 🔐 **Admin-only control** for managing bot behavior and database access
- Uses the [DrissionPage](https://github.com/michiya/DrissionPage) library for parsing OLX pages.


## 💻 How to Use

### 1. Clone the Repository

Clone the repository to your local machine:

```bash
git clone https://github.com/ChuprinaDaria/OLX_Scrapper_To_telegram_bot.git
cd OLX_Scrapper_To_telegram_bot
``` 

## 2. Install Dependencies

Install the necessary Python packages:

```bash
pip install -r requirements.txt
```

### 3. Create and Configure .env File

The bot relies on several environment variables to function properly. Create a .env file in the root of the project and add the following variables:

```bash
TELEGRAM_TOKEN=
CHAT_IDS=-1000000000,-1001000000
ADMIN_IDS=0000000,000000
DB_FILE=olx_ads.db
URLS_FILE=tracked_urls.json

```

### Example

- `TELEGRAM_TOKEN`: Your Telegram bot token (get it from BotFather on Telegram).
- `CHAT_IDS`: A comma-separated list of chat IDs where the bot will send ads (you can get the chat ID from @userinfobot).
-  DB_FILE
-  URLS_FILE=tracked_urls.json

### 4. Run the Bot

After configuring the environment variables, you can run the bot:

```bash
python bot.py
```

The bot will start checking for new ads and send them to the specified Telegram channels.

### 🛠️ Configuration

The bot includes a set of optimized scanning parameters that you can tweak directly in the source code to suit your needs.
Here’s what you can customize:
# Scanning settings – optimized
QUICK_CHECK_INTERVAL = 15      # Time (in seconds) between quick scans
MIN_INTERVAL = 20              # Minimum wait time after a scan
MAX_INTERVAL = 40              # Maximum wait time if nothing found
MAX_AD_AGE_MINUTES = 50        # Only ads newer than this (in minutes) will be processed
VERY_FRESH_AD_MINUTES = 10     # Ads fresher than this are marked "🔥 VERY FRESH"
SKIP_FIRST_N_ADS = 2           # Skip first N promoted ads (usually sponsored)
MAX_CARDS_TO_CHECK = 13        # How many listings to process per scan
SCROLL_COUNT = 4               # Page scroll depth before parsing
MAX_PARALLEL_URLS = 3          # Max URLs to scan in parallel
PAGE_LOAD_TIMEOUT = 40         # Time (in seconds) to wait for full page load
DETAILED_LOGGING = True        # Enable verbose logs for the first N cards
CONSECUTIVE_OLD_COUNT = 3      # Stop parsing if this many old ads are found in a row
EARLY_EXIT_ON_OLD = True       # Stop scan early if old listings are detected


- The list of OLX URLs to monitor by updating `OLX_URLS`.
- The hashtags for categories in the `CATEGORY_HASHTAGS` dictionary.
- The check interval between ad checks in `CHECK_INTERVAL`.

### 💬 Example Output

Here is an example of how the bot sends an ad to your Telegram channel:

```
📌 oddam za darmo skrzynie ze sklejki palety CID628
⏱️ 46.8 min ago
📆 23 maja 2025
🔗 View Ad
```

### 🎯 Contribution

If you'd like to contribute to this project, feel free to submit a pull request or open an issue.

# Attention: This project was created for personal use for educational purposes (searching for a free refrigerator))))

### 📄 License

This project is licensed under the MIT License.
