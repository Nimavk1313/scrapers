import time
import os
import signal
import sys
import pandas as pd
import threading
import select
import tty
import termios
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page
from bs4 import BeautifulSoup

# --- Tanzimat-e Avvalieh ---
URL = "https://app.growthmentor.com/search"
OUTPUT_FILENAME = "growthmentor_mentors"

# <<<<<<< MENTOR LIMIT CONFIGURATION >>>>>>>
# Set the maximum number of mentors to collect (0 = no limit)
MAX_MENTORS = 5000  # Change this to limit mentors (e.g., 50, 100, 200)

# <<<<<<< RESUME FEATURE CONFIGURATION >>>>>>>
# Set to True to resume from last mentor in existing CSV file
RESUME_FROM_CSV = True  # Set to False to start fresh

# <<<<<<< INTERRUPT HANDLING >>>>>>>
# Global variables for interrupt handling
scraped_data = []
current_browser = None
stop_scraping = False
keyboard_thread = None

# <<<<<<< 1. CHROME PROFILE CONFIGURATION >>>>>>>
# Your Chrome profile path (automatically configured based on your system)
# Profile Path: /Users/Nomercya/Library/Application Support/Google/Chrome/Profile 1

def get_key():
    """Get a single keypress from the user (cross-platform)"""
    try:
        # For Unix-like systems (macOS, Linux)
        if sys.platform != 'win32':
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            try:
                tty.setraw(sys.stdin.fileno())
                ch = sys.stdin.read(1)
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            return ch
        else:
            # For Windows
            import msvcrt
            return msvcrt.getch().decode('utf-8')
    except:
        return None

def keyboard_listener():
    """Listen for keyboard input in a separate thread"""
    global stop_scraping
    
    print("\n⌨️  Press any key to stop scraping and save progress...")
    
    while not stop_scraping:
        try:
            key = get_key()
            if key:
                print(f"\n🛑 Key '{key}' pressed! Stopping scraping and saving progress...")
                stop_scraping = True
                break
        except:
            time.sleep(0.1)
            continue

def signal_handler(signum, frame):
    """Handle Ctrl+C interrupt - save data and exit"""
    global scraped_data, current_browser, stop_scraping
    
    print("\n🛑 Ctrl+C pressed! Saving data and exiting...")
    stop_scraping = True
    
    # Save all scraped data
    if scraped_data:
        try:
            save_data(scraped_data, OUTPUT_FILENAME, append_mode=RESUME_FROM_CSV)
            print(f"✅ Saved {len(scraped_data)} mentors to CSV file")
        except Exception as e:
            print(f"❌ Error saving data: {e}")
    else:
        print("⚠️  No data to save")
    
    # Close browser
    if current_browser:
        try:
            current_browser.close()
            print("✅ Browser closed")
        except Exception as e:
            print(f"⚠️  Error closing browser: {e}")
    
    print("👋 Program terminated by user")
    sys.exit(0)

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
    """Find and click the Load More button using multiple methods with Playwright"""
    # Method 1: Try the exact CSS selector
    try:
        button = page.locator("button.tw-inline-flex.tw-cursor-pointer.tw-select-none.tw-items-center.tw-justify-center.tw-font-medium.tw-outline-none.tw-transition-all.tw-px-4.tw-py-2.tw-text-sm.tw-rounded-full")
        if button.is_visible() and button.is_enabled():
            return button
    except:
        pass
    
    # Method 2: Try partial class matching
    try:
        button = page.locator("button[class*='tw-inline-flex'][class*='tw-cursor-pointer']")
        if button.is_visible() and button.is_enabled():
            return button
    except:
        pass
    
    # Method 3: Try XPath for button with specific classes
    try:
        button = page.locator("//button[contains(@class, 'tw-inline-flex') and contains(@class, 'tw-cursor-pointer') and contains(@class, 'tw-rounded-full')]")
        if button.is_visible() and button.is_enabled():
            return button
    except:
        pass
    
    # Method 4: Try finding button by text content
    try:
        button = page.locator("//button[contains(text(), 'Load more') or contains(text(), 'Show more') or contains(text(), 'More')]")
        if button.is_visible() and button.is_enabled():
            return button
    except:
        pass
    
    # Method 5: Try the old selector as fallback
    try:
        button = page.locator("div.tw-mt-8.tw-text-center > button")
        if button.is_visible() and button.is_enabled():
            return button
    except:
        pass
    
    return None

def read_existing_csv():
    """Read existing CSV file and return all existing mentor names"""
    csv_path = f"{OUTPUT_FILENAME}.csv"
    
    try:
        if not os.path.exists(csv_path):
            print("📄 No existing CSV file found. Starting fresh.")
            return set()
        
        df = pd.read_csv(csv_path)
        if df.empty:
            print("📄 Existing CSV file is empty. Starting fresh.")
            return set()
        
        existing_names = set(df['Name'].tolist())
        total_existing = len(df)
        print(f"📄 Found existing CSV with {total_existing} mentors")
        print(f"🔄 Will skip any mentors already in CSV")
        
        return existing_names
        
    except Exception as e:
        print(f"⚠️  Error reading existing CSV: {e}")
        print("📄 Starting fresh.")
        return set()

def scrape_growthmentor(page, url, existing_names=None):
    """Estekhraj-e etela'at az site-e GrowthMentor using Playwright"""
    global scraped_data, stop_scraping
    
    print(f"🚀 Loading GrowthMentor directly: {url}")
    
    if existing_names:
        print(f"🔄 Will skip {len(existing_names)} existing mentors")
    
    # Clear scraped data at start
    scraped_data = []
    stop_scraping = False
    
    # Navigate to the URL with Playwright
    try:
        print("📍 Navigating to GrowthMentor...")
        page.goto(url, wait_until="domcontentloaded")
        
        # Wait for page to load
        page.wait_for_load_state("networkidle", timeout=30000)
        
        current_url = page.url
        page_title = page.title()
        
        print(f"✅ Page loaded successfully!")
        print(f"📍 Current URL: {current_url}")
        print(f"📄 Page Title: {page_title}")
        
        # Verify we're on GrowthMentor
        if "growthmentor.com" in current_url:
            print("✅ Confirmed: On GrowthMentor website!")
        else:
            print(f"⚠️  Warning: Not on GrowthMentor page. Current URL: {current_url}")
            
    except Exception as e:
        print(f"❌ Error loading GrowthMentor: {e}")
        raise Exception(f"Failed to load GrowthMentor: {e}")
    
    # Additional wait to ensure page is fully loaded
    print("⏳ Waiting for page to fully load...")
    page.wait_for_timeout(5000)  # Wait 5 seconds
    
    # Check if we need to login
    try:
        # Look for login indicators
        login_elements = page.locator("//a[contains(text(), 'Login') or contains(text(), 'Sign in')]")
        if login_elements.count() > 0:
            print("⚠️  Login required! Please log in to GrowthMentor in your Chrome browser first.")
            print("After logging in, close Chrome completely and run this script again.")
            return []
        else:
            print("✅ Already logged in or no login required!")
    except Exception as e:
        print(f"Could not check login status: {e}")
    
    # Check page content
    try:
        page_content = page.content()
        if "mentor" in page_content.lower() or "growth" in page_content.lower():
            print("✅ Page content looks correct - found mentor/growth keywords")
        else:
            print("⚠️  Page content might not be loading correctly")
            print("Page content length:", len(page_content))
    except Exception as e:
        print(f"Could not check page content: {e}")

    print("Shروع click kardan roye dokme-ye 'Load more mentors'...")
    if MAX_MENTORS > 0:
        print(f"🎯 Target: Collecting {MAX_MENTORS} NEW mentors (skipping existing ones)")
    else:
        print("🎯 Target: Collecting all available NEW mentors")
    
    click_count = 0
    max_clicks = 100  # Increased safety limit
    new_mentors_found = 0
    
    while click_count < max_clicks and not stop_scraping:
        try:
            # Check if user wants to stop
            if stop_scraping:
                print("🛑 Stop signal received! Saving progress...")
                break
                
            # Check current mentors on page
            current_mentors = page.locator("div.tw-rounded-2xl.tw-bg-white.tw-shadow-sm.dark\\:tw-bg-neutral-800.tw-p-5").all()
            print(f"📊 Total mentors on page: {len(current_mentors)}")
            
            # Count new mentors (not in existing CSV)
            if existing_names:
                new_mentors_count = 0
                for mentor_element in current_mentors:
                    try:
                        name_element = mentor_element.locator("h2.tw-text-2xl.tw-font-bold").first
                        if name_element.is_visible():
                            mentor_name = name_element.text_content().strip()
                            if mentor_name not in existing_names:
                                new_mentors_count += 1
                    except:
                        continue
                
                print(f"📊 New mentors found: {new_mentors_count}")
                
                # Check if we have enough new mentors
                if MAX_MENTORS > 0 and new_mentors_count >= MAX_MENTORS:
                    print(f"✅ Found {new_mentors_count} new mentors (target: {MAX_MENTORS})! Stopping...")
                    break
            
            # Try to find and click Load More button
            load_more_button = find_and_click_load_more_button(page)
            
            if load_more_button is None:
                print("Digar dokme-ye 'Load more' peyda nashod. Tamam-e mentorha load shodan.")
                break
            
            # Scroll to the button with better positioning
            print(f"Scrolling to Load More button (click {click_count + 1})...")
            load_more_button.scroll_into_view_if_needed()
            page.wait_for_timeout(2000)  # Wait for scroll to complete
            
            # Additional scroll to ensure button is fully visible
            page.evaluate("window.scrollBy(0, -100)")
            page.wait_for_timeout(1000)
            
            # Try to click the button
            try:
                # First try regular click
                load_more_button.click()
                print(f"✅ Dokme click shod (click {click_count + 1})...")
            except Exception as click_error:
                print(f"Regular click failed: {click_error}")
                # Fallback to JavaScript click
                page.evaluate("arguments[0].click();", load_more_button)
                print(f"✅ Dokme click shod ba JavaScript (click {click_count + 1})...")
            
            click_count += 1
            
            # Wait for new content to load
            print("Waiting for new mentors to load...")
            page.wait_for_timeout(5000)
            
        except Exception as e:
            print(f"Yek moshkel dar click kardan pish amad: {e}")
            print("Trying to find button again...")
            page.wait_for_timeout(3000)
            continue
    
    if click_count >= max_clicks:
        print(f"Maximum click limit reached ({max_clicks}). Stopping to prevent infinite loop.")
    
    # Check if stopped by user
    if stop_scraping:
        print("🛑 Scraping stopped by user. Extracting and saving current progress...")
        
        # Extract mentors that are currently visible on the page
        print("Parse kardan-e HTML-e jari...")
        soup = BeautifulSoup(page.content(), 'html.parser')
        
        MENTOR_CARD_SELECTOR = "div.tw-rounded-2xl.tw-bg-white.tw-shadow-sm.dark\\:tw-bg-neutral-800.tw-p-5"
        mentor_cards = soup.select(MENTOR_CARD_SELECTOR)
        
        print(f"Tedad-e nahayi {len(mentor_cards)} mentor peyda shod. Dar hale estekhraj...")
        
        # Filter out existing mentors and apply limit
        new_mentors = []
        for card in mentor_cards:
            profile_link_element = card.select_one("a.tw-order-2")
            if profile_link_element:
                name_element = profile_link_element.select_one("h2.tw-text-2xl.tw-font-bold")
                if name_element:
                    mentor_name = name_element.text.strip()
                    if not existing_names or mentor_name not in existing_names:
                        new_mentors.append(card)
                        
                        # Stop if we've reached the limit
                        if MAX_MENTORS > 0 and len(new_mentors) >= MAX_MENTORS:
                            break
        
        print(f"📊 Found {len(new_mentors)} new mentors to save (skipped {len(mentor_cards) - len(new_mentors)} existing)")
        
        # Extract data from new mentors
        extracted_data = []
        for i, card in enumerate(new_mentors, 1):
            profile_link_element = card.select_one("a.tw-order-2")
            if profile_link_element and profile_link_element.has_attr('href'):
                profile_link = profile_link_element['href']
                name = profile_link_element.select_one("h2.tw-text-2xl.tw-font-bold").text.strip() if profile_link_element.select_one("h2.tw-text-2xl.tw-font-bold") else "N/A"
            else:
                profile_link = "N/A"
                name = "N/A"
                
            title = card.select_one("div.tw-text-neutral-600").text.strip() if card.select_one("div.tw-text-neutral-600") else "N/A"
            
            features_dict = {}
            feature_groups = card.select("div[data-title]")
            for group in feature_groups:
                category = group['data-title']
                spans = group.select("span")
                if spans:
                    features_list = [span.text.strip() for span in spans]
                    features_dict[category] = ", ".join(features_list)
            
            row = {
                "Name": name,
                "Profile Link": profile_link,
                "Title": title,
                "Expertise": features_dict.get("Expertise", "N/A"),
                "Tools": features_dict.get("Tools", "N/A"),
                "Industry": features_dict.get("Industry", "N/A")
            }
            extracted_data.append(row)
            scraped_data.append(row)  # Add to global data
        
        # Save the extracted data
        if extracted_data:
            try:
                save_data(extracted_data, OUTPUT_FILENAME, append_mode=RESUME_FROM_CSV)
                print(f"✅ Saved {len(extracted_data)} mentors to CSV file")
            except Exception as e:
                print(f"❌ Error saving data: {e}")
        else:
            print("⚠️  No new mentors found to save")
            
        return extracted_data

    print("Parse kardan-e HTML-e nahayi...")
    soup = BeautifulSoup(page.content(), 'html.parser')
    
    MENTOR_CARD_SELECTOR = "div.tw-rounded-2xl.tw-bg-white.tw-shadow-sm.dark\\:tw-bg-neutral-800.tw-p-5"
    
    mentor_cards = soup.select(MENTOR_CARD_SELECTOR)
    
    data = []
    print(f"Tedad-e nahayi {len(mentor_cards)} mentor peyda shod. Dar hale estekhraj...")

    # Filter out existing mentors and apply limit
    new_mentors = []
    for card in mentor_cards:
        profile_link_element = card.select_one("a.tw-order-2")
        if profile_link_element:
            name_element = profile_link_element.select_one("h2.tw-text-2xl.tw-font-bold")
            if name_element:
                mentor_name = name_element.text.strip()
                if not existing_names or mentor_name not in existing_names:
                    new_mentors.append(card)
                    
                    # Stop if we've reached the limit
                    if MAX_MENTORS > 0 and len(new_mentors) >= MAX_MENTORS:
                        break
    
    print(f"📊 Found {len(new_mentors)} new mentors (skipped {len(mentor_cards) - len(new_mentors)} existing)")
    
    if not new_mentors:
        print("❌ No new mentors found. All mentors on page are already in CSV.")
        return []

    for i, card in enumerate(new_mentors, 1):
        profile_link_element = card.select_one("a.tw-order-2")
        if profile_link_element and profile_link_element.has_attr('href'):
            profile_link = profile_link_element['href']
            name = profile_link_element.select_one("h2.tw-text-2xl.tw-font-bold").text.strip() if profile_link_element.select_one("h2.tw-text-2xl.tw-font-bold") else "N/A"
        else:
            profile_link = "N/A"
            name = "N/A"
            
        title = card.select_one("div.tw-text-neutral-600").text.strip() if card.select_one("div.tw-text-neutral-600") else "N/A"
        
        features_dict = {}
        feature_groups = card.select("div[data-title]")
        for group in feature_groups:
            category = group['data-title']
            spans = group.select("span")
            if spans:
                features_list = [span.text.strip() for span in spans]
                features_dict[category] = ", ".join(features_list)
        
        row = {
            "Name": name,
            "Profile Link": profile_link,
            "Title": title,
            "Expertise": features_dict.get("Expertise", "N/A"),
            "Tools": features_dict.get("Tools", "N/A"),
            "Industry": features_dict.get("Industry", "N/A")
        }
        data.append(row)
        scraped_data.append(row)  # Add to global data for interrupt handling
        
        # Show progress every 10 mentors
        if i % 10 == 0 or i == len(new_mentors):
            print(f"📊 Progress: {i}/{len(new_mentors)} new mentors processed")
        
    return data

def save_data(data, filename, append_mode=False):
    """Zakhire kardan-e dadeha dar format-haye CSV va JSON"""
    if not data:
        print("Hich dade-i baraye zakhire kardan peyda nashod.")
        return

    df = pd.DataFrame(data)
    csv_path = f"{filename}.csv"
    
    if append_mode and os.path.exists(csv_path):
        # Append to existing CSV
        existing_df = pd.read_csv(csv_path)
        combined_df = pd.concat([existing_df, df], ignore_index=True)
        combined_df.to_csv(csv_path, index=False, encoding='utf-8-sig')
        print(f"✅ {len(data)} new mentors added to existing CSV file {csv_path}")
        print(f"📊 Total mentors in CSV: {len(combined_df)}")
    else:
        # Create new CSV
        df.to_csv(csv_path, index=False, encoding='utf-8-sig')
        print(f"✅ Etela'at ba movafaghiat dar file {csv_path} zakhire shod.")

    # Always overwrite JSON with complete data
    json_path = f"{filename}.json"
    if append_mode and os.path.exists(csv_path):
        # Use the combined data for JSON
        combined_df = pd.read_csv(csv_path)
        combined_df.to_json(json_path, orient='records', indent=4, force_ascii=False)
    else:
        df.to_json(json_path, orient='records', indent=4, force_ascii=False)
    print(f"✅ Etela'at ba movafaghiat dar file {json_path} zakhire shod.")

def main():
    """Tabe-ye asli baraye ejraye barnameh"""
    global current_browser, keyboard_thread, stop_scraping
    
    print("--- GrowthMentor Scraper (v21 - Key Press Stop) ---")
    print("🔒 Using Chromium browser with Playwright")
    print(f"🎯 Target URL: {URL}")
    if MAX_MENTORS > 0:
        print(f"📊 Mentor Limit: {MAX_MENTORS} mentors")
    else:
        print("📊 Mentor Limit: No limit (collect all)")
    
    if RESUME_FROM_CSV:
        print("🔄 Resume Mode: Will continue from last mentor in CSV")
    else:
        print("🔄 Fresh Start: Will start from beginning")
    
    print("🛑 Press Ctrl+C to stop and save all data")
    print("⌨️  Press any key to stop scraping and save progress")
    print()
    
    # Set up signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)
    
    # Start keyboard listener thread
    stop_scraping = False
    keyboard_thread = threading.Thread(target=keyboard_listener, daemon=True)
    keyboard_thread.start()
    
    # Check for existing CSV if resume is enabled
    existing_names = set()
    if RESUME_FROM_CSV:
        existing_names = read_existing_csv()
    
    browser = None
    try:
        print("🚀 Starting Playwright with Chromium...")
        browser, page = get_browser_and_page()
        current_browser = browser  # Set global browser for interrupt handling
        
        # Debug: Show initial state
        print("🔍 Initial browser state:")
        print(f"   Current URL: {page.url}")
        print(f"   Page Title: {page.title()}")
        
        # Check user agent
        user_agent = page.evaluate("navigator.userAgent")
        print(f"   User Agent: {user_agent}")
        
        print("🎯 Navigating to GrowthMentor...")
        result_data = scrape_growthmentor(page, URL, existing_names)
        
        # Check if scraping was stopped early and data was already saved
        if stop_scraping:
            if result_data:
                print(f"🎉 Scraping stopped by user! Found and saved {len(result_data)} new mentors.")
            else:
                print("❌ Scraping stopped by user, but no new data was found.")
        else:
            # Normal completion
            if scraped_data:
                print(f"🎉 Scraping completed! Found {len(scraped_data)} new mentors.")
                save_data(scraped_data, OUTPUT_FILENAME, append_mode=RESUME_FROM_CSV)
            else:
                print("❌ No new data was scraped.")
    
    except Exception as e:
        print(f"❌ Error: {e}")
        print("Make sure Chrome is closed and Playwright is installed:")
        print("pip install playwright && playwright install chromium")
        
    finally:
        # Stop keyboard listener
        stop_scraping = True
        if keyboard_thread and keyboard_thread.is_alive():
            keyboard_thread.join(timeout=1)
        
        if browser:
            try:
                browser.close()
                print("✅ Browser closed.")
            except Exception as e:
                print(f"⚠️  Error closing browser: {e}")

if __name__ == "__main__":
    main()
