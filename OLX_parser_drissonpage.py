import os
import time
import logging
from DrissionPage import ChromiumPage
import telebot
from dotenv import load_dotenv
from datetime import datetime

# Specify the correct path to the .env file
env_path = os.path.join(os.path.dirname(__file__), '.env')
print(f"Loading environment variables from: {env_path}")

# Check if the file exists
if not os.path.exists(env_path):
    print(f".env file not found at {env_path}")
    print("Files in the current directory:")
    print(os.listdir(os.path.dirname(env_path)))
    raise FileNotFoundError(f".env file not found at {env_path}")

# Load environment variables from the specified file
load_dotenv(dotenv_path=env_path)

# Diagnostics: Print the contents of the .env file
with open(env_path, 'r') as file:
    print("Contents of the .env file:")
    print(file.read())

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 🔧 Settings (Use environment variables or a config file)
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_IDS = os.getenv('CHAT_IDS').split(',')
OLX_URLS = [
    'https://www.olx.pl/YOUR_PAGE',
    'https://www.olx.pl/YOUR_PAGE',
    'https://www.olx.pl/YOUR_PAGE',
    'https://www.olx.pl/YOUR_PAGE',
    'https://www.olx.pl/YOUR_PAGE',
    'https://www.olx.pl/YOUR_PAGE',
    'https://www.olx.pl/YOUR_PAGE',
]
CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', '180'))

# Add diagnostic messages
print(f"TELEGRAM_TOKEN: {TELEGRAM_TOKEN}")
print(f"CHAT_IDS: {CHAT_IDS}")
print(f"OLX_URLS: {OLX_URLS}")
print(f"CHECK_INTERVAL: {CHECK_INTERVAL}")

# Check if environment variables were loaded correctly
if not TELEGRAM_TOKEN or not CHAT_IDS or not OLX_URLS or not CHECK_INTERVAL:
    raise ValueError("Not all environment variables are loaded. Please check the .env file")

bot = telebot.TeleBot(TELEGRAM_TOKEN)
sent_ads = set()  # Avoid duplicates

# Initialize ChromiumPage
driver = ChromiumPage()

# Function to truncate text
def truncate_text(text, max_length):
    if len(text) > max_length:
        return text[:max_length] + '...'
    return text

# Function to extract tags from the ad page
def extract_tags():
    tags = []
    tag_elements = driver.eles('css:li.css-1r0si1e')  # This is a guess; update it based on the actual structure
    # Add more specific selectors if needed
    if not tag_elements:
        tag_elements = driver.eles('css:li[data-testid="ad-attributes"]')
    for tag in tag_elements:
        tags.append(tag.text)
    return tags

# Function to extract category from the ad page
def extract_category():
    category_element = driver.ele('css:span.css-1b6t4dn')  # This is a guess; update it based on the actual structure
    if category_element:
        return category_element.text
    return "No category"

# Function to extract the publication date from the ad page
def extract_publication_date():
    date_element = driver.ele('css:div[data-cy="ad-posted-at"]')
    if date_element:
        date_text = date_element.text
        # Assuming the date_text format is like "10/03/2025 | 09:22"
        return date_text
    return "Unknown date"

# Map categories to hashtags
CATEGORY_HASHTAGS = {
    "YOUR CATEGORY": "#CATEGORY", 
    "YOUR CATEGORY": "#CATEGORY",
    "YOUR CATEGORY": "#CATEGORY",
    "YOUR CATEGORY": "#CATEGORY",
    "YOUR CATEGORY": "#CATEGORY",
    "YOUR CATEGORY": "#CATEGORY",
    "YOUR CATEGORY": "#CATEGORY",
}

# URL to hashtag mapping
URL_HASHTAGS = {
    'https://www.olx.pl/YOUR_PAGE': '#HASHTAG', 
    'https://www.olx.pl/YOUR_PAGE': '#HASHTAG',  
    'https://www.olx.pl/YOUR_PAGE': '#HASHTAG',  
    'https://www.olx.pl/YOUR_PAGE': '#HASHTAG',  
    'https://www.olx.pl/YOUR_PAGE': '#HASHTAG',  
    'https://www.olx.pl/YOUR_PAGE': '#HASHTAG',  
    'https://www.olx.pl/YOUR_PAGE': '#HASHTAG',  
}

# 🔧 Function to fetch ads using DrissionPage
def get_new_ads(url):
    logging.info("🔍 Launching DrissionPage to fetch ads from URL: %s", url)

    # Open the OLX URL using driver
    driver.get(url)
    logging.info("🌐 Opened OLX URL: %s", url)

    # Scroll to load more ads on OLX
    for i in range(15):  # Increase the number of scrolls
        driver.scroll.down(500)
        logging.info(f"⬇️ Scrolled down {i+1} times")
        time.sleep(2)  # Increase the delay to allow more content to load

    # First try to find ads using different selectors
    ads = driver.eles('css:a[data-cy="listing-ad-title"]')  # Main selector
    if not ads:
        ads = driver.eles('css:a[data-testid="ad-title"]')  # Alternative selector 1
    if not ads:
        ads = driver.eles('css:a[href*="/d/oferta/"]')  # Alternative selector 2
    if not ads:
        ads = driver.eles('css:a[href^="/d/oferta/"]')  # Alternative selector 3

    logging.info("🔎 Number of ads found: %d", len(ads))

    if not ads:
        logging.warning("⚠️ OLX did not load any ads.")
        return []

    new_ads = []

    for ad in ads:
        try:
            link = ad.attr('href')
            if link:
                link = link.replace("m.olx.pl", "www.olx.pl")  # Replace mobile domain
                if "olx.pl" not in link:
                    logging.info("⏩ Skipping non-OLX link: %s", link)
                    continue  # Skip non-OLX links

                logging.info("🔗 Ad link: %s", link)

                # Open the ad page
                driver.get(link)
                time.sleep(3)

                title_element = driver.ele('css:h1')
                title = title_element.text if title_element else "Untitled"
                image_element = driver.ele('css:img')
                image = image_element.attr('src') if image_element else "https://via.placeholder.com/300"
                description_element = driver.ele('css:div[data-cy="ad_description"]')
                description = description_element.text if description_element else "No description"
                publication_date = extract_publication_date()
                tags = extract_tags()
                category = extract_category()
                category_hashtag = CATEGORY_HASHTAGS.get(category, "")
                tags_str = ' '.join([f'#{tag.replace(" ", "_")}' for tag in tags])
                url_hashtag = URL_HASHTAGS.get(url, "")

                logging.info("Found tags: %s", tags)  # Log found tags
                logging.info("Found category: %s", category)  # Log found category

                # Truncate title and description
                title = truncate_text(title, 50)
                description = truncate_text(description, 200)

                new_ads.append({'title': title, 'link': link, 'image': image, 'description': description, 'tags': tags_str, 'category': category_hashtag, 'url_hashtag': url_hashtag, 'publication_date': publication_date})
                logging.info("🔎 Title: %s, Link: %s, Image: %s, Description: %s, Tags: %s, Category: %s, URL Hashtag: %s, Publication Date: %s", title, link, image, description, tags_str, category_hashtag, url_hashtag, publication_date)
            else:
                logging.warning("⚠️ Ad link is None")

        except Exception as e:
            logging.error("⚠️ Error fetching ad: %s", e)

    logging.info("✅ Found %d new ads from URL: %s", len(new_ads), url)
    return new_ads

# 📤 Function to send ads to the channel
def send_ads_to_channel():
    all_ads = []
    for url in OLX_URLS:
        all_ads.extend(get_new_ads(url))

    if not all_ads:
        logging.warning("⚠️ No new ads. Waiting...")
        return

    for ad in all_ads:
        if ad['link'] in sent_ads:
            logging.info("⏩ Skipping duplicate: %s", ad['title'])
            continue  # Skip duplicates

        try:
            # Modify caption format
            if ad['title'] == "Untitled":
                caption = f"📌 {ad['description']}\n📆 {ad['publication_date']}\n\n🔗 [Visit site]({ad['link']})\n\n{ad['tags']} {ad['category']} {ad['url_hashtag']}"
            else:
                caption = f"📌 **{ad['title']}**\n📌 {ad['description']}\n📆 {ad['publication_date']}\n\n🔗 [Visit site]({ad['link']})\n\n{ad['tags']} {ad['category']} {ad['url_hashtag']}"
                
            for chat_id in CHAT_IDS:
                logging.info("📤 Sending to Telegram chat_id: %s, title: %s", chat_id, ad['title'])
                bot.send_photo(chat_id.strip(), ad['image'], caption=caption, parse_mode="Markdown")
            sent_ads.add(ad['link'])  # Add to sent list
            time.sleep(2)
        except telebot.apihelper.ApiException as e:
            logging.error("❌ Error sending to Telegram: %s", e)

# 🔄 Run the bot in a loop
while True:
    logging.info("🔄 Checking for new ads...")
    send_ads_to_channel()
    logging.info("⏳ Waiting %d seconds...\n", CHECK_INTERVAL)
    time.sleep(CHECK_INTERVAL)