# OLX Ads Monitoring Telegram Bot

A Python-based Telegram bot that automatically monitors free ads on OLX and sends the freshest ads to specified Telegram chats. 

## 🚀 Features

📡 Monitors new listings on OLX and OTOMOTO in real time, only sending the freshest ads
📤 Automatically posts listings to Telegram chats, with or without images, using Markdown formatting
🛠️ Built-in admin panel directly in Telegram — add, view, or delete tracked URLs without touching the code
⚙️ Configured via a .env file — store your bot token, chat IDs, and other settings safely
🚀 Uses DrissionPage for fast, stealthy scraping without full Selenium overhead
🔁 Supports parallel checking of multiple URLs for better performance
🧠 Smart interval handling — checks more frequently if new ads are found
💾 SQLite database with deduplication, expiry tracking, and auto-cleanup
👥 Supports multiple Telegram chat IDs
🔐 Admin-only access to bot commands and management features
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

You can configure:

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
