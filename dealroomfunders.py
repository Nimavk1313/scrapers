import time
import pandas as pd
import json
import os
import signal
import sys
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page
from bs4 import BeautifulSoup

# --- Configuration ---
URL = "https://dealroom.launchvic.org/transactions/f/all_slug_locations/anyof_~victoria_1~"
OUTPUT_FILENAME = "dealroom_victoria_funders"

# <<<<<<< FUNDER LIMIT CONFIGURATION >>>>>>>
# Set the maximum number of funders to collect (0 = no limit)
MAX_FUNDERS = 0  # Change this to limit funders (e.g., 50, 100, 200)

# Credentials file path
CREDENTIALS_FILE = "dealroom_credentials.json"

# Global variable to store collected data
collected_funder_data = []

# <<<<<<< 1. CHROME PROFILE CONFIGURATION >>>>>>>
# Your Chrome profile path (automatically configured based on your system)
# Profile Path: /Users/Nomercya/Library/Application Support/Google/Chrome/Profile 1

def save_credentials(username, password):
    """Save login credentials to file"""
    credentials = {
        "username": username,
        "password": password
    }
    with open(CREDENTIALS_FILE, 'w') as f:
        json.dump(credentials, f)
    print(f"✅ Credentials saved to {CREDENTIALS_FILE}")

def load_credentials():
    """Load saved credentials from file"""
    if os.path.exists(CREDENTIALS_FILE):
        try:
            with open(CREDENTIALS_FILE, 'r') as f:
                credentials = json.load(f)
            return credentials.get("username"), credentials.get("password")
        except Exception as e:
            print(f"⚠️ Error loading credentials: {e}")
    return None, None

def handle_login(page):
    """Handle login process for DealRoom"""
    print("🔐 Checking if login is required...")
    
    # Check if we're already logged in by looking for user-specific elements
    try:
        # Look for elements that indicate we're logged in
        user_elements = page.locator("//a[contains(@href, 'profile') or contains(@href, 'account') or contains(@href, 'dashboard')]")
        if user_elements.count() > 0:
            print("✅ Already logged in!")
            return True
    except:
        pass
    
    # Check for login form elements
    try:
        login_form = page.locator("form").first
        if login_form.is_visible():
            print("🔐 Login form detected. Attempting to login...")
            
            # Try to load saved credentials
            username, password = load_credentials()
            
            if username and password:
                print("📁 Using saved credentials...")
                try:
                    # Fill login form
                    username_field = page.locator("input[type='email'], input[name='email'], input[name='username'], input[placeholder*='email'], input[placeholder*='Email']").first
                    password_field = page.locator("input[type='password'], input[name='password']").first
                    
                    if username_field.is_visible() and password_field.is_visible():
                        username_field.fill(username)
                        password_field.fill(password)
                        
                        # Click login button
                        login_button = page.locator("button[type='submit'], input[type='submit'], button:has-text('Login'), button:has-text('Sign in'), button:has-text('Log in')").first
                        if login_button.is_visible():
                            login_button.click()
                            page.wait_for_timeout(3000)
                            
                            # Check if login was successful
                            if not page.locator("form").first.is_visible():
                                print("✅ Login successful!")
                                return True
                            else:
                                print("❌ Login failed. Please check credentials.")
                                return False
                except Exception as e:
                    print(f"❌ Error during login: {e}")
                    return False
            else:
                print("❌ No saved credentials found. Please login manually in the browser.")
                print("After logging in, the credentials will be saved for future use.")
                input("Press Enter after you have logged in manually...")
                
                # Save credentials after manual login
                try:
                    username_input = input("Enter your username/email: ")
                    password_input = input("Enter your password: ")
                    save_credentials(username_input, password_input)
                    return True
                except KeyboardInterrupt:
                    print("❌ Login cancelled.")
                    return False
    except Exception as e:
        print(f"Could not detect login form: {e}")
    
    print("✅ No login required or already logged in.")
    return True

def get_browser_and_page():
    """Initialize Playwright browser with Chromium"""
    print("🔒 Using Chromium browser with Playwright")
    print("📁 Profile Path: /Users/Nomercya/Library/Application Support/Google/Chrome/Profile 1")
    
    playwright = sync_playwright().start()
    
    try:
        print("🚀 Initializing Playwright with Chromium...")
        
        # Launch browser with Chromium (default Playwright browser)
        browser = playwright.chromium.launch_persistent_context(
            user_data_dir="/Users/Nomercya/Library/Application Support/Google/Chrome",
            headless=False,  # Set to True if you want headless mode
            args=[
                "--profile-directory=Profile 1",
                "--start-maximized",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage"
            ],
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
        )
        
        print("✅ Playwright initialized with Chromium!")
        
        # Get the first page (or create a new one)
        page = browser.pages[0] if browser.pages else browser.new_page()
        
        # Set timeouts
        page.set_default_timeout(60000)  # 60 seconds
        page.set_default_navigation_timeout(60000)
        
        return browser, page
        
    except Exception as e:
        print(f"❌ CRITICAL ERROR: Failed to initialize Playwright with Chromium!")
        print(f"Error details: {e}")
        print("\n🔧 TROUBLESHOOTING STEPS:")
        print("1. Make sure Chrome is completely closed")
        print("2. Check if the profile path exists:")
        print("   /Users/Nomercya/Library/Application Support/Google/Chrome/Profile 1")
        print("3. Try running Chrome manually first to ensure the profile works")
        print("4. Check if you have permission to access the Chrome profile directory")
        print("5. Install Playwright: pip install playwright && playwright install chromium")
        print("\n❌ This scraper uses Chromium with your Chrome profile.")
        playwright.stop()
        raise Exception("Cannot initialize Playwright with Chromium. Please fix the installation and try again.")


def find_and_click_load_more_button(page):
    """Find and click the Load More button for DealRoom"""
    # Try multiple selectors for load more button
    selectors = [
        "button:has-text('Load more')",
        "button:has-text('Show more')",
        "button:has-text('More')",
        "//button[contains(text(), 'Load more') or contains(text(), 'Show more') or contains(text(), 'More')]",
        "button[class*='load']",
        "button[class*='more']",
        ".load-more",
        ".show-more"
    ]
    
    for selector in selectors:
        try:
            button = page.locator(selector).first
            if button.is_visible() and button.is_enabled():
                return button
        except:
            continue
    
    return None


def scrape_dealroom(page, url):
    """Scrape funder data from DealRoom Victoria using Playwright"""
    print(f"🚀 Loading DealRoom Victoria: {url}")
    
    # Navigate to the URL with Playwright
    try:
        print("📍 Navigating to DealRoom Victoria...")
        page.goto(url, wait_until="domcontentloaded")
        
        current_url = page.url
        page_title = page.title()
        
        print(f"✅ Page loaded successfully!")
        print(f"📍 Current URL: {current_url}")
        print(f"📄 Page Title: {page_title}")
        
        # Verify we're on DealRoom
        if "dealroom.launchvic.org" in current_url:
            print("✅ Confirmed: On DealRoom Victoria website!")
        else:
            print(f"⚠️  Warning: Not on DealRoom page. Current URL: {current_url}")
            
    except Exception as e:
        print(f"❌ Error loading DealRoom: {e}")
        raise Exception(f"Failed to load DealRoom: {e}")
    
    # Handle login if required
    if not handle_login(page):
        print("❌ Login failed. Cannot proceed with scraping.")
        return []
    
    # Additional wait to ensure page is fully loaded
    print("⏳ Waiting for page to fully load...")
    page.wait_for_timeout(5000)  # Wait 5 seconds
    
    # Check page content
    try:
        page_content = page.content()
        if "table-list-item" in page_content.lower():
            print("✅ Page content looks correct - found funder cards")
        else:
            print("⚠️  Page content might not be loading correctly")
            print("Page content length:", len(page_content))
    except Exception as e:
        print(f"Could not check page content: {e}")

    print("🔄 Loading more funders...")
    if MAX_FUNDERS > 0:
        print(f"🎯 Target: Collecting up to {MAX_FUNDERS} funders")
    else:
        print("🎯 Target: Collecting all available funders")
    
    # Simple scroll and collect all funders
    print("📜 Scrolling and collecting all funders...")
    global collected_funder_data
    all_funder_data = []
    scroll_count = 0
    max_scrolls = 5000  # Maximum scroll attempts
    
    while scroll_count < max_scrolls:
        # Extract data from all currently visible funders
        soup = BeautifulSoup(page.content(), 'html.parser')
        visible_cards = soup.select("div.table-list-item")
        
        print(f"📊 Scroll {scroll_count + 1}: Found {len(visible_cards)} funder cards")
        
        for card in visible_cards:
            try:
                # Extract name
                name_element = card.select_one("div.name a")
                name = name_element.text.strip() if name_element else "-"
                
                # Check if we already have this funder
                if not any(funder.get("Name") == name for funder in all_funder_data):
                    # Extract all data
                    investors = []
                    investors_container = card.select_one("div.table-list-column.investors")
                    if investors_container:
                        investor_links = investors_container.select("ul li a")
                        investors = [link.text.strip() for link in investor_links if link.text.strip()]
                    investors_text = ", ".join(investors) if investors else "-"
                    
                    market = []
                    market_container = card.select_one("div.table-list-column.market")
                    if market_container:
                        market_links = market_container.select("ul li a")
                        market = [link.text.strip() for link in market_links if link.text.strip()]
                    market_text = ", ".join(market) if market else "-"
                    
                    location_element = card.select_one("div.table-list-column.locations span")
                    location = location_element.text.strip() if location_element else "-"
                    
                    round_valuation_element = card.select_one("div.table-list-column.roundValuation")
                    round_valuation = round_valuation_element.text.strip() if round_valuation_element else "-"
                    
                    last_round_element = card.select_one("div.table-list-column._amount div div")
                    last_round = last_round_element.text.strip() if last_round_element else "-"
                    
                    date_element = card.select_one("div.table-list-column.date")
                    date = date_element.text.strip() if date_element else "-"
                    
                    latest_valuation_element = card.select_one("div.table-list-column.valuation")
                    latest_valuation = latest_valuation_element.text.strip() if latest_valuation_element else "-"
                
                    funder_data = {
                        "Name": name,
                        "Investors": investors_text,
                        "Market": market_text,
                        "Location": location,
                        "Round Valuation": round_valuation,
                        "Last Round": last_round,
                        "Date": date,
                        "Latest Valuation": latest_valuation
                    }
                    
                    all_funder_data.append(funder_data)
                    collected_funder_data.append(funder_data)  # Store in global variable
                    print(f"✅ Added: {name}")
                    
            except Exception as e:
                print(f"Error extracting funder data: {e}")
                continue
        
        print(f"📊 Total unique funders collected: {len(all_funder_data)}")
        
        # Check if we've reached the limit
        if MAX_FUNDERS > 0 and len(all_funder_data) >= MAX_FUNDERS:
            print(f"✅ Reached target limit of {MAX_FUNDERS} funders!")
            break
        
        # Scroll down to load more content
        print("📜 Scrolling down...")
        page.keyboard.press("PageDown")
        page.wait_for_timeout(3000)  # Wait 3 seconds
        
        scroll_count += 1
    
    print(f"🎉 Scrolling completed! Collected {len(all_funder_data)} unique funders")
    return all_funder_data

def save_data(data, filename):
    """Save scraped data to CSV and JSON formats"""
    if not data:
        print("No data found to save.")
        return

    df = pd.DataFrame(data)
    csv_path = f"{filename}.csv"
    df.to_csv(csv_path, index=False, encoding='utf-8-sig')
    print(f"✅ Data successfully saved to {csv_path}")

    json_path = f"{filename}.json"
    df.to_json(json_path, orient='records', indent=4, force_ascii=False)
    print(f"✅ Data successfully saved to {json_path}")

def save_partial_data():
    """Save any collected data when browser closes or script is interrupted"""
    global collected_funder_data
    if collected_funder_data:
        print("💾 Saving partial data before closing...")
        save_data(collected_funder_data, f"{OUTPUT_FILENAME}_partial")
        print(f"✅ Partial data saved: {len(collected_funder_data)} funders")
    else:
        print("📝 No data to save.")

def signal_handler(signum, frame):
    """Handle Ctrl+C and other interruption signals"""
    print("\n🛑 Script interrupted! Saving collected data...")
    save_partial_data()
    sys.exit(0)

def main():
    """Main function to run the DealRoom Victoria scraper"""
    print("--- DealRoom Victoria Scraper ---")
    print("🔒 Using Chromium browser with Playwright")
    print(f"🎯 Target URL: {URL}")
    if MAX_FUNDERS > 0:
        print(f"📊 Funder Limit: {MAX_FUNDERS} funders")
    else:
        print("📊 Funder Limit: No limit (collect all)")
    print()
    
    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
    signal.signal(signal.SIGTERM, signal_handler)  # Termination signal
    
    browser = None
    try:
        print("🚀 Starting Playwright with Chromium...")
        browser, page = get_browser_and_page()
        
        # Debug: Show initial state
        print("🔍 Initial browser state:")
        print(f"   Current URL: {page.url}")
        print(f"   Page Title: {page.title()}")
        
        # Check user agent
        user_agent = page.evaluate("navigator.userAgent")
        print(f"   User Agent: {user_agent}")
        
        print("🎯 Navigating to DealRoom Victoria...")
        scraped_data = scrape_dealroom(page, URL)
        
        if scraped_data:
            print(f"🎉 Scraping completed! Found {len(scraped_data)} funders.")
            save_data(scraped_data, OUTPUT_FILENAME)
        else:
            print("❌ No data was scraped.")
    
    except Exception as e:
        print(f"❌ Error: {e}")
        print("Make sure Chrome is closed and Playwright is installed:")
        print("pip install playwright && playwright install chromium")
        
    finally:
        # Save any partial data before closing
        save_partial_data()
        
        if browser:
            try:
                browser.close()
                print("✅ Browser closed.")
            except Exception as e:
                print(f"⚠️  Error closing browser: {e}")

if __name__ == "__main__":
    main()
