# OLX Ads Monitoring Telegram Bot\ OLX_Scrapper_To_telegram_bot

A Python-based Telegram bot that automatically monitors free ads on OLX and sends them to a Telegram channel.

## 🚀 Features

- Monitors new listings on OLX based on specified criteria.
- Automatically posts listings to a Telegram channel.
- Supports configuration via an `.env` file for API keys and other settings.
- Uses the [DrissionPage](https://github.com/michiya/DrissionPage) library for parsing OLX pages.
- Customizable check intervals to suit your needs.
- Supports multiple Telegram chat IDs.
- Includes filtering and hashtagging for easy categorization of ads.

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
TELEGRAM_TOKEN=your-telegram-bot-token
CHAT_IDS=123456789,987654321
OLX_URLS=https://www.olx.pl/your-page,https://www.olx.pl/another-page
CHECK_INTERVAL=180
```

### Example

- `TELEGRAM_TOKEN`: Your Telegram bot token (get it from BotFather on Telegram).
- `CHAT_IDS`: A comma-separated list of chat IDs where the bot will send ads (you can get the chat ID from @userinfobot).
- `OLX_URLS`: A list of URLs from OLX that you want to monitor.
- `CHECK_INTERVAL`: How often (in seconds) the bot will check for new ads. The default is 180 seconds.

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
Title: Free bicycle for sale
Description: A used bicycle in good condition, free for pickup.
Date: 10/03/2025
Tags: #bicycle #free #pickup
Category: #sportandhobby
🔗 View Ad
```

### 🎯 Contribution

If you'd like to contribute to this project, feel free to submit a pull request or open an issue.

### 📄 License

This project is licensed under the MIT License.
