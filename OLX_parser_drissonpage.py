import os
import time
import logging
import random
import re
import json
import sqlite3
from datetime import datetime, timedelta
import telebot
from telebot import types
from threading import Lock
from urllib.parse import urlparse, unquote
from env_loader import TELEGRAM_TOKEN, CHAT_IDS, ADMIN_IDS, DB_FILE, URLS_FILE


lock = Lock()  # For thread safety
# Publication date cache
PUBLICATION_DATE_CACHE = {}  # ad_id -> {date_str, minutes_ago, last_check_time}
MAX_CACHE_SIZE = 1000
CACHE_EXPIRY_HOURS = 6



# Scanning settings - optimized
QUICK_CHECK_INTERVAL = 15     # 15 seconds between checks
MIN_INTERVAL = 20             # Minimum interval 20 seconds
MAX_INTERVAL = 40             # Maximum interval (seconds)
MAX_AD_AGE_MINUTES = 50        # Track ads up to 6 minutes old
VERY_FRESH_AD_MINUTES = 10     # Mark as "very fresh" up to 4 minutes
SKIP_FIRST_N_ADS = 2          # Always skip first 2 ads (likely promotions)
MAX_CARDS_TO_CHECK = 13       # Maximum number of cards to check
SCROLL_COUNT = 4              # 2 scrolls for URL is enough
MAX_PARALLEL_URLS = 3         # Maximum parallel URLs
PAGE_LOAD_TIMEOUT = 40        # Page load timeout (seconds)
DETAILED_LOGGING = True       # Detailed logging for first 10 cards
CONSECUTIVE_OLD_COUNT = 3     # Break after this many consecutive old ads
EARLY_EXIT_ON_OLD = True      # Early exit when old ad found



# Initialize Telegram bot
bot = telebot.TeleBot(TELEGRAM_TOKEN)

# Setup logging with UTF-8 support
def setup_logging():
    logging.basicConfig(
        level=logging.INFO, 
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler("bot.log", encoding='utf-8'),
            logging.StreamHandler()
        ]
    )

# Polish month names
POLISH_MONTHS = {
    'stycznia': 1, 'lutego': 2, 'marca': 3, 'kwietnia': 4, 'maja': 5, 'czerwca': 6,
    'lipca': 7, 'sierpnia': 8, 'września': 9, 'października': 10, 'listopada': 11, 'grudnia': 12
}

def is_otomoto_url(url):
    """Check if URL belongs to OTOMOTO."""
    return 'otomoto.pl' in url.lower()

def is_admin(user_id):
    """Check if user is an admin."""
    user_id_str = str(user_id)
    return user_id_str in ADMIN_IDS

def extract_title_from_url(url):
    """Extract ad title from URL."""
    try:
        parsed = urlparse(url)
        path = parsed.path
        
        # Split path into parts
        parts = path.strip('/').split('/')
        
        # Find the part with title (last part before ID)
        for part in parts:
            if 'ID' in part and '-' in part:
                title_with_id = part
                title = title_with_id.split('-ID')[0]
                return unquote(title.replace('-', ' ')).strip()
            
        # If ID not found, try to take the last part
        if parts and len(parts) > 0:
            last_part = parts[-1]
            
            # Remove ID part if exists
            if 'ID' in last_part:
                title = last_part.split('ID')[0]
            else:
                title = last_part
                
            return unquote(title.replace('-', ' ')).strip()
            
    except Exception as e:
        logging.warning(f"Error extracting title from URL: {e}")
    
    return "Unknown title" 

def extract_ad_id_from_url(url):
    """Extract ad ID from URL."""
    # Pattern: ID12345678 or ID12H45AB
    match = re.search(r'ID([a-zA-Z0-9]+)', url)
    if match:
        return match.group(1)
    return None

def load_urls():
    """Load URLs from file."""
    if os.path.exists(URLS_FILE):
        try:
            with open(URLS_FILE, 'r') as f:
                data = json.load(f)
                urls = data.get('urls', [])
                logging.info(f"Loaded {len(urls)} URLs from file")
                return urls
        except Exception as e:
            logging.error(f"Error loading URLs from file: {e}")
    
    # Return empty list if file doesn't exist
    logging.info("No URLs file found, starting with empty list")
    return []

def save_urls(urls):
    """Save URLs to file."""
    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(os.path.abspath(URLS_FILE)), exist_ok=True)
        
        with open(URLS_FILE, 'w') as f:
            json.dump({'urls': urls}, f, indent=2)
        logging.info(f"Saved {len(urls)} URLs to file")
        return True
    except Exception as e:
        logging.error(f"Error saving URLs to file: {e}")
        return False
    
def init_database():
    """Initialize database."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Ads table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS ads (
        link TEXT PRIMARY KEY,
        title TEXT,
        ad_id TEXT,
        site TEXT,
        date_found TIMESTAMP,
        date_published TEXT,
        expiry_date TIMESTAMP
    )
    ''')
    
    # Check if sent_to_telegram column exists in ads table
    cursor.execute("PRAGMA table_info(ads)")
    columns = [column[1] for column in cursor.fetchall()]
    
    # Add sent_to_telegram column if it doesn't exist
    if 'sent_to_telegram' not in columns:
        cursor.execute('ALTER TABLE ads ADD COLUMN sent_to_telegram BOOLEAN DEFAULT 0')
        logging.info("Added sent_to_telegram column to existing database")
    
    # Activity log table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS activity_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        action TEXT,
        url TEXT,
        timestamp TIMESTAMP
    )
    ''')
    
    # Settings table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT,
        updated_at TIMESTAMP
    )
    ''')
    
    # Add last cleanup setting if not exists
    cursor.execute('''
    INSERT OR IGNORE INTO settings (key, value, updated_at) 
    VALUES ('last_cleanup', ?, ?)
    ''', (datetime.now().isoformat(), datetime.now().isoformat()))
    
    # Create indexes for optimization
    cursor.execute('CREATE INDEX IF NOT EXISTS ads_site_idx ON ads(site)')
    cursor.execute('CREATE INDEX IF NOT EXISTS ads_date_found_idx ON ads(date_found)')
    cursor.execute('CREATE INDEX IF NOT EXISTS ads_expiry_idx ON ads(expiry_date)')
    cursor.execute('CREATE INDEX IF NOT EXISTS ads_sent_idx ON ads(sent_to_telegram)')
    
    conn.commit()
    conn.close()
    
    logging.info("Database initialized successfully")
    
    logging.info("Database initialized successfully")

def add_ad_to_db(link, title, site="OLX", ad_id=None, date_published=None):
    """Add ad to database. Returns True if added, False otherwise."""
    now = datetime.now()
    expiry = now + timedelta(days=7)

    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        # Check if ad exists and if it was sent
        cursor.execute("SELECT sent_to_telegram FROM ads WHERE link = ?", (link,))
        result = cursor.fetchone()
        
        if result is not None:
            # Ad exists, update expiry date
            was_sent = bool(result[0])
            cursor.execute(
                '''
                UPDATE ads SET expiry_date = ? WHERE link = ?
                ''',
                (expiry.isoformat(), link)
            )
            conn.commit()
            conn.close()
            logging.info(f"ℹ️ Ad already exists in DB, updated expiry: {link}, was_sent={was_sent}")
            return False, was_sent
        
        # Insert new ad
        cursor.execute(
            '''
            INSERT INTO ads 
            (link, title, ad_id, site, date_found, date_published, expiry_date, sent_to_telegram)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0)
            ''',
            (link, title, ad_id, site, now.isoformat(), date_published, expiry.isoformat())
        )

        # Log activity
        cursor.execute(
            '''
            INSERT INTO activity_log (action, url, timestamp)
            VALUES (?, ?, ?)
            ''',
            ('add', link, now.isoformat())
        )

        conn.commit()
        conn.close()
        logging.info(f"✅ Ad successfully added to DB: {link}")
        return True, False  # Added, not sent yet

    except Exception as e:
        logging.error(f"❌ DB error while adding ad: {e} (link: {link})")
        if conn:
            conn.close()
        return False, False

def mark_ad_as_sent(link):
    """Mark ad as sent to Telegram."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute(
            '''
            UPDATE ads SET sent_to_telegram = 1 WHERE link = ?
            ''',
            (link,)
        )
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logging.error(f"Error marking ad as sent: {e}")
        if conn:
            conn.close()
        return False

def check_ad_sent(link):
    """Check if ad was already sent to Telegram."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute("SELECT sent_to_telegram FROM ads WHERE link = ?", (link,))
        result = cursor.fetchone()
        
        conn.close()
        
        if result is not None:
           return bool(result[0]) if result[0] is not None else False

        
    except Exception as e:
        logging.error(f"Error checking if ad was sent: {e}")
        if conn:
            conn.close()
        return False

def check_ad_exists(link):
    """Check if ad exists in database."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute("SELECT 1 FROM ads WHERE link = ?", (link,))
    exists = cursor.fetchone() is not None
    
    conn.close()
    return exists

def get_unsent_ads():
    """Get ads that exist in DB but weren't sent to Telegram."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute(
            '''
            SELECT link, title, site, ad_id, date_published 
            FROM ads WHERE sent_to_telegram = 0
            '''
        )
        results = cursor.fetchall()
        
        conn.close()
        
        unsent_ads = []
        for link, title, site, ad_id, date_published in results:
            unsent_ads.append({
                'link': link,
                'title': title,
                'site': site,
                'ad_id': ad_id,
                'publication_date': date_published
            })
        
        return unsent_ads
    except Exception as e:
        logging.error(f"Error getting unsent ads: {e}")
        if conn:
            conn.close()
        return []

def cleanup_old_ads():
    """Clean up old ads from database."""
    now = datetime.now()
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Check when last cleanup happened
    cursor.execute("SELECT value FROM settings WHERE key = 'last_cleanup'")
    last_cleanup = datetime.fromisoformat(cursor.fetchone()[0])
    
    # If less than 7 days since last cleanup, skip
    if now - last_cleanup < timedelta(days=7):
        conn.close()
        return False
    
    # Count records before cleanup
    cursor.execute("SELECT COUNT(*) FROM ads")
    before_count = cursor.fetchone()[0]
    
    # Delete expired ads
    cursor.execute("DELETE FROM ads WHERE expiry_date < ?", (now.isoformat(),))
    deleted_count = cursor.rowcount
    
    # Update last cleanup date
    cursor.execute('''
    UPDATE settings SET value = ?, updated_at = ? WHERE key = 'last_cleanup'
    ''', (now.isoformat(), now.isoformat()))
    
    # Optimize database after deletion
    cursor.execute("VACUUM")
    
    conn.commit()
    conn.close()
    
    logging.info(f"Database cleanup completed. Removed {deleted_count} expired ads, {before_count-deleted_count} remaining.")
    return True

def get_ad_stats():
    """Get database statistics."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    stats = {}
    
    # Total ads
    cursor.execute("SELECT COUNT(*) FROM ads")
    stats['total_ads'] = cursor.fetchone()[0]
    
    # Ads by site
    cursor.execute("SELECT site, COUNT(*) FROM ads GROUP BY site")
    stats['by_site'] = {site: count for site, count in cursor.fetchall()}
    
    # Ads in last 24 hours
    yesterday = (datetime.now() - timedelta(days=1)).isoformat()
    cursor.execute("SELECT COUNT(*) FROM ads WHERE date_found > ?", (yesterday,))
    stats['last_24h'] = cursor.fetchone()[0]
    
    # Last cleanup date
    cursor.execute("SELECT value FROM settings WHERE key = 'last_cleanup'")
    stats['last_cleanup'] = cursor.fetchone()[0]
    
    # Recent ads
    cursor.execute("SELECT link, title, date_found FROM ads ORDER BY date_found DESC LIMIT 5")
    stats['recent_ads'] = [
        {'link': link, 'title': title, 'date': date_found} 
        for link, title, date_found in cursor.fetchall()
    ]
    
    # Unsent ads count
    cursor.execute("SELECT COUNT(*) FROM ads WHERE sent_to_telegram = 0")
    stats['unsent_ads'] = cursor.fetchone()[0]
    
    conn.close()
    return stats

def parse_polish_date(date_str):
    """Parse Polish date formats and calculate minutes since publication."""
    if not date_str:
        return float('inf')
        
    now = datetime.now()
    date_str = date_str.lower().strip()
    
    try:
        # Handle "Dzisiaj o HH:MM" format (Today at HH:MM)
        if "dzisiaj o" in date_str:
            time_part = date_str.split("dzisiaj o")[1].strip()
            hours, minutes = map(int, time_part.split(':'))
            pub_date = now.replace(hour=hours, minute=minutes, second=0, microsecond=0)
            
            # If time is in future, it's from yesterday
            if pub_date > now:
                pub_date = pub_date - timedelta(days=1)
                
        # Handle "Wczoraj o HH:MM" format (Yesterday at HH:MM)
        elif "wczoraj o" in date_str:
            time_part = date_str.split("wczoraj o")[1].strip()
            hours, minutes = map(int, time_part.split(':'))
            pub_date = (now - timedelta(days=1)).replace(hour=hours, minute=minutes, second=0, microsecond=0)
            
        # Handle "Odświeżono dnia DD miesiąca YYYY" format (Refreshed on DD month YYYY)
        elif "odświeżono dnia" in date_str or "odświeżono" in date_str:
            date_part = date_str.split("odświeżono dnia" if "odświeżono dnia" in date_str else "odświeżono")[1].strip()
            match = re.search(r'(\d+)\s+(\w+)\s+(\d{4})', date_part)
            if match:
                day = int(match.group(1))
                month_name = match.group(2).lower()
                year = int(match.group(3))
                month = POLISH_MONTHS.get(month_name, now.month)
                pub_date = datetime(year, month, day)
            else:
                logging.debug(f"Failed to match refresh date pattern: {date_part}")
                return float('inf')
            
        # Handle "DD miesiąca YYYY" format (for OTOMOTO and other sites)
        elif any(month in date_str for month in POLISH_MONTHS.keys()):
            match = re.search(r'(\d+)\s+(\w+)(?:\s+(\d{4}))?', date_str)
            if match:
                day = int(match.group(1))
                month_name = match.group(2).lower()
                year = int(match.group(3)) if match.group(3) else now.year
                month = POLISH_MONTHS.get(month_name, now.month)
                
                # Check if time is included (like "25 marca 2025 14:58")
                time_match = re.search(r'(\d{1,2}):(\d{1,2})', date_str)
                if time_match:
                    hours, minutes = int(time_match.group(1)), int(time_match.group(2))
                    pub_date = datetime(year, month, day, hours, minutes)
                else:
                    pub_date = datetime(year, month, day)
                
                # If date seems to be in future, it's probably from last year (if no year was specified)
                if pub_date > now and not match.group(3):
                    pub_date = datetime(now.year - 1, month, day)
            else:
                logging.debug(f"Failed to match month date pattern: {date_str}")
                return float('inf')
            
        # Format not recognized
        else:
            logging.debug(f"Unknown date format: {date_str}")
            return float('inf')
        
        # Calculate minutes since publication
        minutes_ago = (now - pub_date).total_seconds() / 60
        return minutes_ago
        
    except Exception as e:
        logging.warning(f"Error parsing date '{date_str}': {e}")
        return float('inf')

def get_cached_ad_age(ad_id, date_str):
    """Get cached ad age or calculate new one."""
    now = time.time()
    
    # Check cache
    if ad_id and ad_id in PUBLICATION_DATE_CACHE:
        cache_entry = PUBLICATION_DATE_CACHE[ad_id]
        cache_age = (now - cache_entry['last_check_time']) / 60
        
        # If cache is fresh (less than 30 minutes), use it
        if cache_age < 30:
            # Update age based on time passed since caching
            return cache_entry['minutes_ago'] + cache_age
            
    # If no cache or expired, calculate
    minutes_ago = parse_polish_date(date_str)
    
    # Save to cache
    if ad_id:
        PUBLICATION_DATE_CACHE[ad_id] = {
            'date_str': date_str,
            'minutes_ago': minutes_ago,
            'last_check_time': now
        }
        
        # Limit cache size, remove oldest entries
        if len(PUBLICATION_DATE_CACHE) > MAX_CACHE_SIZE:
            # Sort by last check time and remove oldest 20%
            sorted_entries = sorted(PUBLICATION_DATE_CACHE.items(), 
                                   key=lambda x: x[1]['last_check_time'])
            entries_to_remove = sorted_entries[:int(MAX_CACHE_SIZE * 0.2)]
            for key, _ in entries_to_remove:
                del PUBLICATION_DATE_CACHE[key]
    
    return minutes_ago

from DrissionPage import ChromiumPage, ChromiumOptions

# Stable selectors for OLX & OTOMOTO
AD_CARD_SELECTORS = ['css:div[data-cy="l-card"]', 'css:div[data-testid="l-card"]']
LINK_SELECTORS = ['css:a[href*="/oferta/"]', 'css:a[href*="otomoto.pl"]']
IMAGE_SELECTORS = ['css:img[alt]', 'css:img[src]']
DATE_SELECTORS = ['css:p[data-testid="location-date"]']

def create_browser_options():
    """Create browser options."""
    options = ChromiumOptions()
    options.set_user_agent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    options.no_imgs = True  # Don't load images for speed
    options.headless = True  # Headless mode
    options.set_argument("--disable-blink-features=AutomationControlled")
    options.set_argument("--no-sandbox")
    options.set_argument("--disable-dev-shm-usage")
    options.set_argument("--disable-gpu")
    options.set_argument("--disable-extensions")
    options.set_argument("--disable-software-rasterizer")
    return options

def create_and_configure_browser():
    """Create and configure browser for scanning."""
    options = create_browser_options()
    return ChromiumPage(addr_or_opts=options)

def wait_for_page_load(driver, timeout=PAGE_LOAD_TIMEOUT):
    """Wait for page to fully load."""
    start = time.time()
    prev_html = ""
    stable_starts = None

    while time.time() - start < timeout:
        try:
            # Check if driver is connected
            if not hasattr(driver, 'url'):
                logging.warning("Driver is not available")
                return False
                
            # Check DOM stability
            current_html = driver.html

            if current_html == prev_html:
                if stable_starts is None:
                    stable_starts = time.time()
                elif time.time() - stable_starts >= 2:  # Stable for 2 seconds
                    # Check document readiness
                    ready_state = driver.run_js("return document.readyState")
                    if ready_state == "complete":
                        return True
            else:
                stable_starts = None
                prev_html = current_html

            time.sleep(0.5)

        except Exception as e:
            if 'refreshed' in str(e).lower():
                logging.warning("DOM is refreshing, will retry shortly...")
            else:
                logging.warning(f"Error while waiting for page: {e}")
            time.sleep(1)

    logging.warning("Page load timeout exceeded")
    return False

def wait_for_ads(driver, min_cards=8, timeout=20, is_otomoto=False):
    """Wait for minimum number of ad cards to load."""
    selectors = []
    
    if is_otomoto:
        selectors = [
            'css:div.css-1g5933j',
            'css:div.css-1ut25fa',
            'css:div.css-qfzx1y > div',
            'css:div[type="list"].css-1ut25fa',
            'css:div[data-cy="l-card"]',
            'css:div[data-testid="l-card"]'
        ]
    else:
        selectors = [
            'css:div[data-cy="l-card"]',
            'css:div[data-testid="l-card"]',
            'css:.css-l9drzq',
            'css:div.css-qfzx1y > div.css-1g5933j',
            'css:div.css-qfzx1y > div > div.css-1ut25fa',
            'css:div[type="list"].css-1ut25fa'
        ]
    
    start = time.time()
    while time.time() - start < timeout:
        for selector in selectors:
            try:
                cards = driver.eles(selector)
                if cards and len(cards) >= min_cards:
                    logging.info(f"Found {len(cards)} cards using selector: {selector}")
                    return True
            except Exception:
                pass
        time.sleep(0.5)
    
    logging.warning("⚠️ Not enough ad cards loaded after waiting")
    return False

def get_ad_cards(driver, is_otomoto=False):
    """Get all ad cards from current page."""
    # First try main stable selectors
    for selector in AD_CARD_SELECTORS:
        try:
            cards = driver.eles(selector)
            if cards and len(cards) > 0:
                logging.info(f"Found {len(cards)} cards with selector: {selector}")
                return cards
        except Exception:
            pass
    
    # Backup selectors by site type
    backup_selectors = []
    if is_otomoto:
        backup_selectors = [
            'css:div.css-1g5933j',
            'css:div.css-1ut25fa',
            'css:div.css-qfzx1y > div',
            'css:div[type="list"].css-1ut25fa'
        ]
    else:
        backup_selectors = [
            'css:.css-l9drzq',
            'css:div.css-qfzx1y > div.css-1g5933j',
            'css:div.css-qfzx1y > div > div.css-1ut25fa',
            'css:div[type="list"].css-1ut25fa'
        ]
    
    # Try backup selectors
    for selector in backup_selectors:
        try:
            cards = driver.eles(selector)
            if cards and len(cards) > 0:
                logging.info(f"Found {len(cards)} cards with backup selector: {selector}")
                return cards
        except Exception:
            pass
    
    return []

def is_promoted_card(card):
    """Check if card is promoted (TOP OGŁOSZENIE or visual badges)."""
    try:
        # Text badge
        promo_label = card.ele('css:div.baxter-native-lopdwi__attribution')
        if promo_label and 'top ogłoszenie' in promo_label.text.lower():
            return True

        # Visual badge (no text)
        visual_badge = card.ele('css:div.css-qavd0c > div.css-s3yjnp')
        if visual_badge:
            return True

    except Exception:
        pass

    return False  

def extract_date_from_preview(element, is_otomoto=False):
    """Extract date from preview card."""
    for selector in DATE_SELECTORS:
        try:
            date_element = element.ele(selector)
            if date_element and date_element.text:
                # Get full text which includes location and date
                full_text = date_element.text
                # Extract just the date part that comes after the dash
                if " - " in full_text:
                    return full_text.split(" - ")[1].strip()
                return full_text
        except Exception:
            pass
    
    # Fallback to site-specific selectors if main ones fail
    try:
        if is_otomoto:
            # OTOMOTO specific selector
            date_element = element.ele('css:.css-odp1qd p.css-vbz67q')
        else:
            # OLX specific selector
            date_element = element.ele('css:.css-vbz67q')
            
        if date_element and date_element.text:
            date_text = date_element.text
            if " - " in date_text:
                return date_text.split(" - ")[1].strip()
            return date_text
    except Exception:
        pass
    
    return None

def extract_preview_data(card, is_otomoto=False, card_index=None):
    """Extract data from preview card (without opening page)."""
    try:
        # Detailed logging for first 10 cards
        detailed_log = DETAILED_LOGGING and (card_index is not None and card_index < 10)
        
        # Get link - first try stable selectors
        link_element = None
        for selector in LINK_SELECTORS:
            try:
                link_element = card.ele(selector)
                if link_element and link_element.attr('href'):
                    break
            except Exception:
                pass
        
        # If stable selectors didn't work, try fallbacks
        if not link_element or not link_element.attr('href'):
            if is_otomoto:
                link_element = card.ele('css:a.css-1tqlkj0')
            else:
                link_element = card.ele('css:a[href*="/d/oferta/"]') or card.ele('css:a[href^="/d/oferta/"]')
        
        if not link_element:
            if detailed_log:
                logging.warning(f"Card #{card_index}: No link element found")
            return None

        link = link_element.attr('href')
        if not link:
            if detailed_log:
                logging.warning(f"Card #{card_index}: Empty link attribute")
            return None
        
        # Log found link
        if detailed_log:
            logging.info(f"Card #{card_index}: Found link: {link}")
        
        # Format link
        if not link.startswith("http"):
            if is_otomoto:
                link = "https://www.otomoto.pl" + link if link.startswith("/") else "https://www.otomoto.pl/" + link
            else:
                link = "https://www.olx.pl" + link if link.startswith("/") else "https://www.olx.pl/" + link
        
        # Extract ad ID
        ad_id = extract_ad_id_from_url(link)
        
        # Extract title from URL
        title = extract_title_from_url(link)
        if detailed_log:
            logging.info(f"Card #{card_index}: Title: {title}")
        
        # Extract publication date
        date_str = extract_date_from_preview(card, is_otomoto)
        if detailed_log and date_str:
            logging.info(f"Card #{card_index}: Date: {date_str}")
        
        # Extract image (if any)
        image_url = None
        for selector in IMAGE_SELECTORS:
            try:
                img_element = card.ele(selector)
                if img_element:
                    image_url = img_element.attr('src')
                    if image_url and detailed_log:
                        logging.info(f"Card #{card_index}: Found image: {image_url}")
                    if image_url:
                        break
            except Exception:
                pass
        
        # If stable selectors didn't work, try fallbacks
        if not image_url:
            try:
                img_element = card.ele('css:img')
                if img_element:
                    image_url = img_element.attr('src')
                    if detailed_log:
                        logging.info(f"Card #{card_index}: Found image with fallback selector: {image_url}")
            except Exception as e:
                if detailed_log:
                    logging.warning(f"Card #{card_index}: Error extracting image: {e}")
        
        # Collect and return data
        result = {
            'link': link,
            'title': title,
            'ad_id': ad_id,
            'publication_date': date_str,
            'image': image_url,
            'site': "OTOMOTO" if is_otomoto else "OLX"
        }
        
        # Calculate ad age
        if date_str:
            minutes_ago = get_cached_ad_age(ad_id, date_str)
            result['minutes_ago'] = minutes_ago
            
            if detailed_log:
                freshness = "VERY FRESH" if minutes_ago <= VERY_FRESH_AD_MINUTES else (
                    "FRESH" if minutes_ago <= MAX_AD_AGE_MINUTES else "OLD")
                logging.info(f"Card #{card_index}: Ad age: {minutes_ago:.1f} min, Status: {freshness}")
        
        return result
    except Exception as e:
        if detailed_log:
            logging.warning(f"Card #{card_index}: Error extracting preview data: {e}")
        return None

def try_send_from_preview(card, is_otomoto=False, card_index=None):
    """Try to send ad using only preview data."""
    try:
        preview_data = extract_preview_data(card, is_otomoto, card_index)
        if not preview_data:
            logging.info(f"Card #{card_index}: No preview data extracted.")
            return False, False

        if not all(key in preview_data for key in ['link', 'title']):
            logging.warning(f"Card #{card_index}: Missing key info in preview data.")
            return False, False

        link = preview_data['link']
        ad_id = preview_data.get('ad_id')
        minutes_ago = preview_data.get('minutes_ago')

        # Check ad age
        if preview_data.get('publication_date') and minutes_ago is None:
            minutes_ago = get_cached_ad_age(ad_id, preview_data['publication_date'])
            preview_data['minutes_ago'] = minutes_ago

        if minutes_ago is None:
            logging.info(f"Card #{card_index}: Could not determine age, skipping.")
            return False, True

        if minutes_ago > MAX_AD_AGE_MINUTES:
            logging.info(f"Card #{card_index}: Skipping old ad: {minutes_ago:.1f} minutes > {MAX_AD_AGE_MINUTES}")
            return False, True

        # Check if ad already in DB
        if check_ad_exists(link):
            was_sent = check_ad_sent(link)
            if was_sent:
                logging.info(f"Card #{card_index}: Ad already sent: {link}")
                return False, False
            else:
                logging.info(f"Card #{card_index}: Ad exists in DB but not sent — sending now.")
        else:
            logging.info(f"Card #{card_index}: New ad — adding to DB.")
            add_ad_to_db(
                link,
                preview_data.get('title', 'Unknown title'),
                preview_data.get('site', 'OLX'),
                ad_id,
                preview_data.get('publication_date')
            )

        # Send immediately
        sent = send_to_telegram(preview_data)
        return sent, False

    except Exception as e:
        logging.warning(f"Card #{card_index or '?'}: Error in try_send_from_preview: {e}")
        return False, True

    
def send_telegram_message_with_retry(chat_id, message, parse_mode=None, photo=None, max_retries=5, retry_delay=3):
    """Send message to Telegram with retries."""
    for attempt in range(max_retries):
        try:
            if photo:
                return bot.send_photo(chat_id, photo, caption=message, parse_mode=parse_mode)
            else:
                return bot.send_message(chat_id, message, parse_mode=parse_mode)
        except Exception as e:
            is_telegram_error = "telegram" in str(e).lower() or "socket" in str(e).lower() or "connection" in str(e).lower()
            error_type = str(e).split(':')[0]
            
            # Log error
            logging.warning(f"Telegram error (attempt {attempt+1}/{max_retries}): {error_type}")
            
            # If not a Telegram error or last attempt, exit
            if not is_telegram_error or attempt == max_retries - 1:
                logging.error(f"Failed to send message after {attempt+1} attempts: {e}")
                raise
            
            # Otherwise pause before next attempt
            wait_time = retry_delay * (attempt + 1)  # Increase wait time with each attempt
            logging.info(f"Retrying in {wait_time} seconds...")
            time.sleep(wait_time)

def send_to_telegram(ad):
    """Send ad to Telegram with 'very fresh' marking and async delivery."""
    try:
        logging.info(f"📤 Sending to Telegram: {ad['title']}")
        logging.debug(f"📦 FULL AD DATA:\n{json.dumps(ad, indent=2, ensure_ascii=False)}")

        with lock:
            # Mark as sent in DB
            mark_success = mark_ad_as_sent(ad['link'])
            if not mark_success:
                logging.warning(f"⚠️ Could not mark ad as sent in DB: {ad['link']}")

        def send_telegram_async():
            try:
                ad_id = ad.get('ad_id')
                date_str = ad.get('publication_date', '')

                if 'minutes_ago' in ad:
                    minutes_ago = ad['minutes_ago']
                else:
                    minutes_ago = get_cached_ad_age(ad_id, date_str)

                is_very_fresh = isinstance(minutes_ago, (int, float)) and minutes_ago <= VERY_FRESH_AD_MINUTES

                if is_very_fresh:
                    logging.info(f"🔥 VERY FRESH ad detected ({minutes_ago:.1f} min ago)")
                    caption = (
                        f"🔥 *DUŻO ŚWIEŻE!*\n"
                        f"📌 {ad['title']}\n"
                        f"⏱️ {minutes_ago:.1f} min ago\n"
                        f"📆 {ad.get('publication_date', 'Unknown date')}\n\n"
                        f"🔗 {ad['link']}"
                    )
                else:
                    if isinstance(minutes_ago, (int, float)) and minutes_ago > VERY_FRESH_AD_MINUTES <= MAX_AD_AGE_MINUTES:
                        logging.info(f"⚠️ OLX delay: ad published {minutes_ago:.1f} min ago but just appeared")
                    caption = (
                        f"📌 {ad['title']}\n"
                        f"⏱️ {minutes_ago:.1f} min ago\n"
                        f"📆 {ad.get('publication_date', 'Unknown date')}\n\n"
                        f"🔗 {ad['link']}"
                    )

                for chat_id in CHAT_IDS:
                    try:
                        if ad.get('image'):
                            send_telegram_message_with_retry(chat_id, caption, parse_mode="Markdown", photo=ad['image'])
                            logging.info(f"✅ Sent ad with image to {chat_id}: {ad['title']}")
                        else:
                            send_telegram_message_with_retry(chat_id, caption, parse_mode="Markdown")
                            logging.info(f"✅ Sent text-only ad to {chat_id}: {ad['title']}")

                    except Exception as err:
                        logging.error(f"❌ Error sending to Telegram (chat {chat_id}): {err}")

            except Exception as e:
                logging.error(f"🔥 Error in async telegram sending: {e}")

        import threading
        telegram_thread = threading.Thread(target=send_telegram_async)
        telegram_thread.daemon = True
        telegram_thread.start()

        return True

    except Exception as e:
        logging.error(f"🔥 Error sending ad to Telegram: {e}")
        return False

def process_unsent_ads():
    """Process ads that exist in DB but weren't sent to Telegram."""
    unsent_ads = get_unsent_ads()
    if not unsent_ads:
        return 0
    
    sent_count = 0
    logging.info(f"Found {len(unsent_ads)} unsent ads in database, attempting to send...")
    
    for ad in unsent_ads:
        # Check ad age
        if ad.get('publication_date'):
            minutes_ago = get_cached_ad_age(ad.get('ad_id'), ad['publication_date'])
            ad['minutes_ago'] = minutes_ago
            
            # Only send if still fresh
            if minutes_ago <= MAX_AD_AGE_MINUTES * 2:  # Give extra time for unsent ads
                if send_to_telegram(ad):
                    sent_count += 1
                    logging.info(f"✅ Sent previously unsent ad: {ad['title']}")
            else:
                # Mark as sent to avoid future attempts
                mark_ad_as_sent(ad['link'])
                logging.info(f"⏰ Skipping old unsent ad: {ad['title']} ({minutes_ago:.1f} min old)")
        else:
            # If no date, just try to send it
            if send_to_telegram(ad):
                sent_count += 1
                logging.info(f"✅ Sent previously unsent ad (no date): {ad['title']}")
    
    if sent_count > 0:
        logging.info(f"✅ Successfully sent {sent_count} previously unsent ads")
    
    return sent_count    

def quick_check_ads(url, driver):
    logging.info(f"Quick checking URL for fresh ads: {url}")

    is_otomoto = is_otomoto_url(url)
    fresh_found = False
    sent_count = 0
    consecutive_old_count = 0
    promo_processed = 0
    MAX_PROMO_TO_CHECK = 3

    try:
        start_time = time.time()
        driver.get(url)

        if not wait_for_page_load(driver, timeout=PAGE_LOAD_TIMEOUT):
            logging.warning(f"❌ Failed to load page: {url}")
            return False

        if not wait_for_ads(driver, min_cards=8, timeout=10, is_otomoto=is_otomoto):
            logging.warning(f"❌ Cards failed to load for: {url}")
            return False

        try:
            if not is_otomoto:
                driver.run_js("localStorage.setItem('olx-consent', 'true');")
                buttons = driver.eles('css:button[data-role="accept-consent"]')
            else:
                buttons = driver.eles('css:button[id="onetrust-accept-btn-handler"]')
            if buttons:
                buttons[0].click()
                time.sleep(0.5)
        except Exception as e:
            logging.debug(f"Cookie handling skipped: {e}")

        for i in range(SCROLL_COUNT):
            driver.run_js(f"window.scrollTo(0, {(i+1) * 1000});")
            time.sleep(0.7)

        all_cards = get_ad_cards(driver, is_otomoto)
        if not all_cards:
            logging.warning(f"❌ No ad cards found for quick check: {url}")
            return False

        logging.info(f"✅ Found {len(all_cards)} total cards during quick check")

        fresh_in_skipped = False
        for i in range(min(10, len(all_cards))):
            preview = extract_preview_data(all_cards[i], is_otomoto, i)
            if preview:
                logging.info(f"[DEBUG] Card #{i} preview date: {preview.get('publication_date')}, age: {preview.get('minutes_ago')}")
                if i < SKIP_FIRST_N_ADS and preview.get('minutes_ago', float('inf')) <= MAX_AD_AGE_MINUTES:
                    logging.warning(f"⚠️ Found fresh ad in position {i} that would be skipped! Age: {preview.get('minutes_ago'):.1f} min")
                    fresh_in_skipped = True

        skip_count = 0 if fresh_in_skipped else SKIP_FIRST_N_ADS
        cards = all_cards[skip_count:]
        cards_to_process = cards[:MAX_CARDS_TO_CHECK]

        logging.info(f"⏳ Processing {len(cards_to_process)} cards (skipped first {skip_count})")

        process_start = time.time()

        for idx, card in enumerate(cards_to_process):
            card_index = idx + 1

            if is_promoted_card(card):
                if promo_processed >= MAX_PROMO_TO_CHECK:
                    logging.info(f"🚫 Max promoted ads processed ({MAX_PROMO_TO_CHECK}), skipping remaining promos.")
                    continue

                preview = extract_preview_data(card, is_otomoto, card_index)
                if preview and preview.get('minutes_ago', float('inf')) <= MAX_AD_AGE_MINUTES:
                    sent = send_to_telegram(preview)
                    if sent:
                        sent_count += 1
                        promo_processed += 1
                        consecutive_old_count = 0
                        fresh_found = True
                        logging.info(f"✅ Sent promoted ad #{promo_processed}: {preview['title']}")
                else:
                    logging.info(f"⏰ Skipping old promoted ad #{promo_processed + 1}")
                continue  # move to next card

            # regular card processing
            try:
                sent, is_old = try_send_from_preview(card, is_otomoto, card_index)
            except Exception as e:
                logging.error(f"🔥 Error during try_send_from_preview (card #{card_index}): {e}")
                is_old = True

            logging.info(f"🧩 CARD #{card_index}: sent={sent}, is_old={is_old}")

            if sent:
                sent_count += 1
                fresh_found = True
                consecutive_old_count = 0
                logging.info(f"✅ Sent ad #{sent_count} from preview")
            elif is_old:
                consecutive_old_count += 1
                logging.info(f"⏰ Old ad found (#{consecutive_old_count} in a row)")
            else:
                consecutive_old_count = 0

            if (EARLY_EXIT_ON_OLD and is_old) or consecutive_old_count >= CONSECUTIVE_OLD_COUNT:
                logging.critical(f"💥 BREAKING on card #{card_index} - FOUND {consecutive_old_count} CONSECUTIVE OLD ADS")
                break

        process_time = time.time() - process_start
        total_time = time.time() - start_time

        logging.info(f"🏁 Quick check completed for {url}. Sent: {sent_count}. "
                     f"Processing time: {process_time:.2f}s, Total: {total_time:.2f}s")

        return fresh_found

    except Exception as e:
        logging.error(f"❌ Error in quick check for {url}: {e}")
        return False


def quick_check_url(url, options=None):
    """Quick check a single URL for fresh ads."""
    driver = None
    try:
        # Create browser options if not provided
        if options is None:
            options = create_browser_options()
        
        # Create driver
        driver = ChromiumPage(options)

        
        # Run quick check
        fresh_ads_found = quick_check_ads(url, driver)
        
        return fresh_ads_found
    except Exception as e:
        logging.error(f"Error in quick check for URL {url}: {e}")
        return False
    finally:
        # Close driver
        if driver:
            try:
                driver.quit()
            except:
                pass

def quick_check_all_urls():
    """Quick check all URLs for fresh ads."""
    urls = load_urls()
    if not urls:
        logging.info("No URLs to check. Use /addurl command to add URLs.")
        return False

    found_fresh = False
    logging.info(f"Quick checking {len(urls)} URLs for fresh ads")
    start_time = time.time()

    # Limit number of parallel threads, but ensure all URLs are checked
    max_workers = min(MAX_PARALLEL_URLS, len(urls))
    
    # Process any unsent ads first
    unsent_count = process_unsent_ads()
    if unsent_count > 0:
        found_fresh = True
    
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for url in urls:
            # Very short delay to avoid simultaneous requests
            time.sleep(random.uniform(0.1, 0.3))

            # Create new browser options for each thread
            browser_options = create_browser_options()

            # Start quick check in separate thread
            futures.append(executor.submit(quick_check_url, url, browser_options))

        # Check results as they become available
        for future in concurrent.futures.as_completed(futures):
            try:
                if future.result():
                    found_fresh = True
            except Exception as e:
                logging.error(f"Error in quick check thread: {e}")

    # Measure total execution time
    total_time = time.time() - start_time
    logging.info(f"Completed checking all URLs in {total_time:.2f} seconds")

    return found_fresh

def show_admin_menu(chat_id):
    """Show admin menu with URL management buttons."""
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    # Add buttons for URL management
    list_btn = types.InlineKeyboardButton("📋 List URLs", callback_data="listurl")
    add_btn = types.InlineKeyboardButton("➕ Add URL", callback_data="addurl")
    del_btn = types.InlineKeyboardButton("🗑️ Delete URL", callback_data="delurl")
    stats_btn = types.InlineKeyboardButton("📊 Stats", callback_data="dbstats")
    
    markup.add(list_btn, add_btn, del_btn, stats_btn)
    
    bot.send_message(chat_id, "URL Management Options:", reply_markup=markup)

def add_url_from_reply(message):
    """Process reply with URL."""
    if not message.text:
        bot.reply_to(message, "Please send a valid URL.")
        return
        
    process_new_url(message, message.text.strip())

def process_new_url(message, url):
    """Process and validate new URL."""
    if not (url.startswith('http://') or url.startswith('https://')):
        bot.reply_to(message, "Invalid URL format. Please use a complete URL starting with http:// or https://")
        return
    
    # Check if it's an OLX or OTOMOTO URL
    if not ('olx.pl' in url or 'otomoto.pl' in url):
        bot.reply_to(message, "Only OLX or OTOMOTO URLs are supported.")
        return
    
    urls = load_urls()
    if url in urls:
        bot.reply_to(message, f"ℹ️ This URL is already being tracked.")
        return
    
    urls.append(url)
    if save_urls(urls):
        bot.reply_to(message, f"✅ URL added successfully!")
        # Show keyboard with management options
        show_admin_menu(message.chat.id)
    else:
        bot.reply_to(message, f"❌ Failed to add URL. Please try again later.")

# Bot commands
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    """Send welcome message."""
    if is_admin(message.from_user.id):
        welcome_text = (
            "👋 Welcome to OLX/OTOMOTO Monitor Bot!\n\n"
            "Available commands:\n"
            "/addurl [URL] - Add a new URL to monitor\n"
            "/listurl - List all monitored URLs\n"
            "/delurl - Delete a URL from monitoring\n"
            "/dbstats - Show database statistics\n"
            "/cleanup - Force database cleanup\n"
            "/menu - Show admin menu"
        )
        bot.reply_to(message, welcome_text)
        show_admin_menu(message.chat.id)
    else:
        bot.reply_to(message, "⛔ This bot is available only for admins.")

@bot.message_handler(commands=['menu'])
def menu_command(message):
    """Show admin menu."""
    if is_admin(message.from_user.id):
        show_admin_menu(message.chat.id)
    else:
        bot.reply_to(message, "⛔ Sorry, only admins can use this command.")

@bot.message_handler(commands=['addurl'])
def add_url(message):
    """Add URL for monitoring."""
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "⛔ Sorry, only admins can use this command.")
        return
    
    parts = message.text.split(' ', 1)
    if len(parts) < 2:
        # If no URL provided, ask for it using a force reply
        markup = types.ForceReply(selective=True)
        bot.reply_to(message, "Please send the URL you want to add:", reply_markup=markup)
        return
    
    url = parts[1].strip()
    # Remove square brackets if present
    if url.startswith('[') and url.endswith(']'):
        url = url[1:-1]
    
    process_new_url(message, url)

@bot.message_handler(commands=['listurl'])
def list_urls(message):
    """Show list of tracked URLs."""
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "⛔ Sorry, only admins can use this command.")
        return
    
    urls = load_urls()
    if not urls:
        bot.reply_to(message, "ℹ️ No URLs are currently being tracked.")
        return
    
    response = "📋 Currently tracked URLs:\n\n"
    for i, url in enumerate(urls):
        response += f"{i+1}. {url}\n"
    
    bot.reply_to(message, response)

@bot.message_handler(commands=['delurl'])
def delete_url(message):
    """Delete URL from monitoring list."""
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "⛔ Sorry, only admins can use this command.")
        return
    
    urls = load_urls()
    if not urls:
        bot.reply_to(message, "ℹ️ No URLs are currently being tracked.")
        return
    
    # Show URLs with delete buttons
    markup = types.InlineKeyboardMarkup(row_width=1)
    for i, url in enumerate(urls):
        # Truncate URL if too long
        display_url = url[:50] + "..." if len(url) > 50 else url
        btn = types.InlineKeyboardButton(f"🗑️ {i+1}. {display_url}", callback_data=f"del_{i}")
        markup.add(btn)
    
    bot.reply_to(message, "Select URL to delete:", reply_markup=markup)

@bot.message_handler(commands=['dbstats'])
def db_stats_command(message):
    """Show database statistics."""
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "⛔ Sorry, only admins can use this command.")
        return
    
    stats = get_ad_stats()
    response = (
        "📊 Database Statistics:\n\n"
        f"Total ads tracked: {stats['total_ads']}\n"
        f"Ads in last 24 hours: {stats.get('last_24h', 'N/A')}\n"
        f"Unsent ads: {stats.get('unsent_ads', 'N/A')}\n"
        f"Last cleanup: {stats['last_cleanup']}\n\n"
        "By site:\n"
    )
    
    for site, count in stats.get('by_site', {}).items():
        response += f"- {site}: {count} ads\n"
    
    if stats.get('recent_ads'):
        response += "\nRecent ads:\n"
        for ad in stats['recent_ads']:
            response += f"- {ad['title']} (added {ad['date']})\n"
    
    bot.reply_to(message, response)

@bot.message_handler(commands=['cleanup'])
def cleanup_command(message):
    """Perform database cleanup."""
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "⛔ Sorry, only admins can use this command.")
        return
    
    if cleanup_old_ads():
        bot.reply_to(message, "✅ Database cleanup completed successfully.")
    else:
        bot.reply_to(message, "ℹ️ Database was cleaned recently, skipping cleanup.")

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    """Handle callback queries from inline buttons."""
    logging.info(f"Callback received: {call.data} from user {call.from_user.id}")
    
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ Only admins can use these options.")
        return
        
    if call.data == "listurl":
        # Show list of URLs
        urls = load_urls()
        if not urls:
            bot.answer_callback_query(call.id, "No URLs are being tracked.")
            bot.send_message(call.message.chat.id, "ℹ️ No URLs are currently being tracked.")
            return
            
        response = "📋 Currently tracked URLs:\n\n"
        for i, url in enumerate(urls):
            response += f"{i+1}. {url}\n"
        
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, response)
        
    elif call.data == "addurl":
        # Prompt to add URL
        bot.answer_callback_query(call.id)
        markup = types.ForceReply(selective=True)
        msg = bot.send_message(call.message.chat.id, "Please send the URL you want to add:", reply_markup=markup)
        bot.register_for_reply(msg, add_url_from_reply)
        
    elif call.data == "delurl":
        # Show URLs with delete buttons
        urls = load_urls()
        if not urls:
            bot.answer_callback_query(call.id, "No URLs to delete.")
            return
            
        markup = types.InlineKeyboardMarkup(row_width=1)
        for i, url in enumerate(urls):
            # Truncate URL if too long
            display_url = url[:50] + "..." if len(url) > 50 else url
            btn = types.InlineKeyboardButton(f"🗑️ {i+1}. {display_url}", callback_data=f"del_{i}")
            markup.add(btn)
            
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "Select URL to delete:", reply_markup=markup)
        
    elif call.data == "dbstats":
        # Show database stats
        stats = get_ad_stats()
        response = (
            "📊 Database Statistics:\n\n"
            f"Total ads tracked: {stats['total_ads']}\n"
            f"Ads in last 24 hours: {stats.get('last_24h', 'N/A')}\n"
            f"Unsent ads: {stats.get('unsent_ads', 'N/A')}\n"
            f"Last cleanup: {stats['last_cleanup']}\n\n"
            "By site:\n"
        )
        
        for site, count in stats.get('by_site', {}).items():
            response += f"- {site}: {count} ads\n"
        
        if stats.get('recent_ads'):
            response += "\nRecent ads:\n"
            for ad in stats['recent_ads'][:3]:  # Show only 3 latest for compactness
                response += f"- {ad['title']} (added {ad['date']})\n"
        
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, response)
        
    elif call.data.startswith("del_"):
        # Delete URL by index
        try:
            idx_str = call.data.split("_")[1]
            index = int(idx_str)
            
            urls = load_urls()
            
            if 0 <= index < len(urls):
                removed_url = urls.pop(index)
                
                if save_urls(urls):
                    bot.answer_callback_query(call.id, "URL deleted successfully.")
                    bot.send_message(call.message.chat.id, f"✅ URL removed successfully:\n{removed_url}")
                else:
                    bot.answer_callback_query(call.id, "Failed to delete URL.")
                    bot.send_message(call.message.chat.id, "❌ Error saving changes.")
            else:
                bot.answer_callback_query(call.id, "Invalid URL index.")
                bot.send_message(call.message.chat.id, f"❌ Error: Invalid index {index}")
        except Exception as e:
            logging.error(f"URL deletion error: {e}")
            bot.answer_callback_query(call.id, "Error during deletion.")
            bot.send_message(call.message.chat.id, f"❌ Error: {str(e)}")

def bot_polling_thread():
    """Thread for handling Telegram bot commands."""
    while True:
        try:
            bot.polling(none_stop=True, interval=3)
        except Exception as e:
            logging.error(f"Bot polling error: {e}")
            time.sleep(10)

def main():
    """Main function to run the bot."""
    try:
        # Create necessary directories
        os.makedirs('./profiles', exist_ok=True)
        
        # Setup logging
        setup_logging()
        
        # Initialize database
        init_database()
        
        # Clean up old records
        cleanup_old_ads()
        
        # Create thread for handling Telegram commands
        import threading
        bot_thread = threading.Thread(target=bot_polling_thread, daemon=True)
        bot_thread.start()
        
        # Startup message
        urls = load_urls()
        site_types = []
        if any('olx.pl' in url for url in urls):
            site_types.append("OLX")
        if any('otomoto.pl' in url for url in urls):
            site_types.append("OTOMOTO")
        
        site_msg = " & ".join(site_types) if site_types else "No sites"
        
        for chat_id in CHAT_IDS:
            try:
                if not urls:
                    startup_msg = "🤖 Bot started, but no URLs configured. Please add URLs with /addurl command."
                else:
                    startup_msg = f"🤖 {site_msg} Monitor started - looking for listings less than {MAX_AD_AGE_MINUTES} minutes old"
                
                bot.send_message(chat_id, startup_msg)
                
                # Info about available commands
                help_msg = (
                    "Available admin commands:\n"
                    "/addurl [URL] - Add a new URL to monitor\n"
                    "/listurl - List all monitored URLs\n"
                    "/delurl - Delete a URL from monitoring\n"
                    "/dbstats - Show database statistics\n"
                    "/cleanup - Force database cleanup\n"
                    "/menu - Show admin menu"
                )
                bot.send_message(chat_id, help_msg)
            except Exception as e:
                logging.error(f"Failed to send startup message: {e}")
        
        # Show menu for all admins
        for admin_id in ADMIN_IDS:
            try:
                show_admin_menu(admin_id)
            except Exception as e:
                logging.error(f"Failed to send admin menu to {admin_id}: {e}")
        
        # Process any unsent ads on startup
        process_unsent_ads()
        
        # Main bot cycle - optimized for more frequent checks
        cycle_counter = 1
        last_stats_time = time.time()
        
        while True:
            try:
                # Measure cycle start time
                start_time = time.time()
                
                logging.info(f"Starting cycle #{cycle_counter}")
                
                # Quick check
                fresh_ads_found = quick_check_all_urls()
                
                # Log stats every 100 cycles
                if cycle_counter % 100 == 0 or time.time() - last_stats_time > 3600:  # every 100 cycles or hour
                    stats = get_ad_stats()
                    logging.info(f"Stats after {cycle_counter} cycles: {stats['total_ads']} total ads, " +
                                f"{stats.get('last_24h', 'N/A')} in last 24h")
                    last_stats_time = time.time()
                
                # Calculate time spent on cycle
                elapsed = time.time() - start_time
                
                # Adaptive wait time considering execution time
                if fresh_ads_found:
                    # If fresh ads found, check again sooner
                    wait_time = max(5, QUICK_CHECK_INTERVAL - elapsed)
                    logging.info(f"Fresh ads detected! Checking again in {wait_time:.1f} seconds (cycle took {elapsed:.1f}s)")
                else:
                    # Standard interval if nothing new
                    wait_time = max(10, MIN_INTERVAL - elapsed)
                    logging.info(f"No fresh ads. Waiting {wait_time:.1f} seconds (cycle took {elapsed:.1f}s)")
                
                # Wait until next check
                if wait_time > 0:
                    time.sleep(wait_time)
                    
                cycle_counter += 1
                
            except Exception as e:
                logging.error(f"Error in main loop: {e}")
                time.sleep(20)  # Wait on error
                
    except Exception as e:
        logging.critical(f"Critical error in main function: {e}")
        for chat_id in CHAT_IDS:
            try:
                bot.send_message(chat_id, f"❌ Bot crashed with error: {e}\nRestart required.")
            except:
                pass


if __name__ == "__main__":
    main()
