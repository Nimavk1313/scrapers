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
URL = "https://www.pif.gov.sa/en/our-investments/our-portfolio/"
OUTPUT_FILENAME = "pif_investors"

# <<<<<<< INVESTOR LIMIT CONFIGURATION >>>>>>>
# Set the maximum number of investors to collect (0 = no limit)
MAX_INVESTORS = 0  # Change this to limit investors (e.g., 50, 100, 200) - 0 = no limit

# <<<<<<< RESUME FEATURE CONFIGURATION >>>>>>>
# Set to True to resume from last investor in existing CSV file
RESUME_FROM_CSV = True  # Set to False to start fresh

# <<<<<<< SPEED CONFIGURATION >>>>>>>
# Set to True to skip portfolio extraction for maximum speed
SKIP_PORTFOLIO_EXTRACTION = False  # Set to True for faster scraping

# <<<<<<< BACKGROUND MODE CONFIGURATION >>>>>>>
# Set to True to run in background (no browser window)
RUN_IN_BACKGROUND = False  # Set to False to see browser window

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
            print(f"✅ Saved {len(scraped_data)} investors to CSV file")
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
        browser_args = [
            "--profile-directory=Profile 1",
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage"
        ]
        
        if RUN_IN_BACKGROUND:
            browser_args.extend([
                "--no-sandbox",
                "--disable-gpu",
                "--disable-extensions"
            ])
        else:
            browser_args.append("--start-maximized")
        
        browser = playwright.chromium.launch(
            headless=RUN_IN_BACKGROUND,  # Use background mode setting
            args=browser_args
        )
        
        # Create a new context
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
        )
        
        print("✅ Playwright initialized with Chromium!")
        
        # Get the first page (or create a new one)
        page = context.new_page()
        
        # Set timeouts - increased for PIF
        page.set_default_timeout(30000)  # 30 seconds
        page.set_default_navigation_timeout(30000)
        
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

# Load more button functionality removed - not needed for re-create.com

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
        print(f"📄 Found existing CSV with {total_existing} investors")
        print(f"🔄 Will skip any investors already in CSV")
        
        return existing_names
        
    except Exception as e:
        print(f"⚠️  Error reading existing CSV: {e}")
        print("📄 Starting fresh.")
        return set()


def scrape_pif_investors_pagination(page, base_url, existing_names=None, start_page=2, end_page=7):
    """Scrape investors from multiple pages using pagination"""
    global scraped_data, stop_scraping
    
    print(f"🔄 Starting pagination scraping from page {start_page} to {end_page}")
    
    all_investors_data = []
    
    for page_num in range(start_page, end_page + 1):
        if stop_scraping:
            print("🛑 Pagination stopped by user")
            break
            
        # Handle URL construction properly for PIF (uses hash-based pagination)
        # Page 1: #ourportfolio_e=0, Page 2: #ourportfolio_e=18, Page 3: #ourportfolio_e=36, etc.
        # Pattern: each page increments by 18
        portfolio_e_value = (page_num - 1) * 18
        page_url = f"{base_url}#ourportfolio_e={portfolio_e_value}"
        print(f"\n📄 Scraping page {page_num}: {page_url}")
        
        try:
            # For hash-based pagination, use JavaScript to change the hash
            if page_num == 2:
                # First time navigating to hash-based page, go to base URL first
                page.goto(base_url, wait_until="domcontentloaded")
                page.wait_for_load_state("domcontentloaded", timeout=15000)
                page.wait_for_timeout(3000)
            
            # Use JavaScript to navigate to the hash
            page.evaluate(f"window.location.hash = 'ourportfolio_e={portfolio_e_value}'")
            
            # Wait for the hash change to trigger content loading
            page.wait_for_timeout(5000)  # Wait for dynamic content to load
            
            # Wait for any dynamic content to load
            try:
                page.wait_for_selector("ul.search-result-list li", timeout=10000)
            except:
                pass  # Continue even if selector not found
            
            # Parse the page
            soup = BeautifulSoup(page.content(), 'html.parser')
            
            # Find investor containers using the same logic as the main function
            selectors_to_try = [
                "ul.search-result-list li",  # Direct li elements (PRIORITY)
                "div.component.search-results.search-results-container.grid-view.col-12.initialized",
                "ul.search-result-list",
                "li",
                "div.grid-container",
                "div[class*='search-result']",
                "div[class*='grid']",
                "div[class*='card']",
                "article",
                "div[class*='investor']"
            ]
            
            investor_containers = []
            for selector in selectors_to_try:
                elements = soup.select(selector)
                if elements and len(elements) > len(investor_containers):
                    investor_containers = elements
            
            if not investor_containers:
                print(f"⚠️  No investor containers found on page {page_num}")
                continue
                
            print(f"📊 Found {len(investor_containers)} investor containers on page {page_num}")
            
            # If we found li elements directly, use them instead of containers
            if investor_containers and investor_containers[0].name == 'li':
                print(f"Found {len(investor_containers)} li elements directly - using these for extraction")
                page_investors_data = extract_investor_data_from_li_elements(investor_containers, existing_names)
            else:
                # Extract data from containers
                page_investors_data = extract_investor_data_from_containers(investor_containers, existing_names)
            
            all_investors_data.extend(page_investors_data)
            
            if page_investors_data:
                print(f"✅ Extracted {len(page_investors_data)} investors from page {page_num}")
            else:
                print(f"⚠️  No new investors found on page {page_num}")
                # If we're on the last page and no new investors found, stop pagination
                if page_num == end_page:
                    print(f"🏁 Reached last page ({end_page}) with no new investors. Stopping pagination.")
                    break
                
        except Exception as e:
            print(f"❌ Error scraping page {page_num}: {e}")
            continue
    
    print(f"\n🎉 Pagination completed! Total new investors found: {len(all_investors_data)}")
    return all_investors_data

def scrape_pif_investors(page, url, existing_names=None):
    """Extract investor data from PIF portfolio page using Playwright"""
    global scraped_data, stop_scraping
    
    print(f"🚀 Loading PIF portfolio page: {url}")
    
    if existing_names:
        print(f"🔄 Will skip {len(existing_names)} existing investors")
    
    # Clear scraped data at start
    scraped_data = []
    stop_scraping = False
    
    # Navigate to the URL with Playwright
    try:
        print("📍 Navigating to PIF portfolio page...")
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        
        # Wait for page to load - increased timeout for PIF
        page.wait_for_load_state("domcontentloaded", timeout=30000)
        
        current_url = page.url
        page_title = page.title()
        
        print(f"✅ Page loaded successfully!")
        print(f"📍 Current URL: {current_url}")
        print(f"📄 Page Title: {page_title}")
        
        # Verify we're on PIF website
        if "pif.gov.sa" in current_url:
            print("✅ Confirmed: On PIF website!")
        else:
            print(f"⚠️  Warning: Not on PIF page. Current URL: {current_url}")
            
    except Exception as e:
        print(f"❌ Error loading PIF: {e}")
        raise Exception(f"Failed to load PIF: {e}")
    
    # Additional wait to ensure page is fully loaded
    print("⏳ Waiting for page to fully load...")
    page.wait_for_timeout(3000)  # Wait 3 seconds for dynamic content
    
    # Check page content
    try:
        page_content = page.content()
        if "portfolio" in page_content.lower() or "pif" in page_content.lower():
            print("✅ Page content looks correct - found portfolio/pif keywords")
        else:
            print("⚠️  Page content might not be loading correctly")
            print("Page content length:", len(page_content))
    except Exception as e:
        print(f"Could not check page content: {e}")

    print("Starting to extract investors from PIF portfolio page...")
    if MAX_INVESTORS > 0:
        print(f"🎯 Target: Collecting {MAX_INVESTORS} NEW investors (skipping existing ones)")
    else:
        print("🎯 Target: Collecting all available NEW investors")
    
    # Scroll down to load all investors
    print("Scrolling to load all investors...")
    
    # Scroll down to load all investors - optimized for speed
    last_height = page.evaluate("document.body.scrollHeight")
    scroll_attempts = 0
    max_scroll_attempts = 15  # Increased for PIF page
    
    while scroll_attempts < max_scroll_attempts and not stop_scraping:
        # Check if user wants to stop
        if stop_scraping:
            print("🛑 Stop signal received! Saving progress...")
            break
            
        # Scroll down
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(2000)  # Wait 2 seconds for content to load
        
        # Check if new content loaded
        new_height = page.evaluate("document.body.scrollHeight")
        if new_height == last_height:
            print("No more content to load")
            break
            
        last_height = new_height
        scroll_attempts += 1
        print(f"Scroll attempt {scroll_attempts}/{max_scroll_attempts}")
    
    # Check if stopped by user
    if stop_scraping:
        print("🛑 Scraping stopped by user. Extracting and saving current progress...")
        
        # Extract investors that are currently visible on the page
        print("Parsing current HTML...")
        soup = BeautifulSoup(page.content(), 'html.parser')
        
        # Debug: Let's see what elements we can find
        print("Debug: Looking for investor-related elements...")
        
        # Try different selectors for PIF portfolio structure
        selectors_to_try = [
            "div.component.search-results.search-results-container.grid-view.col-12.initialized",  # Main container
            "ul.search-result-list",  # List of investors
            "li",  # Individual investor items
            "div.grid-container",  # Grid container for investor cards
            "div[class*='search-result']",  # Any search result elements
            "div[class*='grid']",  # Any grid elements
            "div[class*='card']",  # Any card elements
            "article",  # Article elements
            "div[class*='investor']"  # Any investor-related elements
        ]
        
        investor_containers = []
        for selector in selectors_to_try:
            elements = soup.select(selector)
            print(f"Selector '{selector}': Found {len(elements)} elements")
            if elements and len(elements) > len(investor_containers):
                investor_containers = elements
                print(f"Using selector: {selector} (found {len(elements)} elements)")
        
        # Extract investor data from containers
        extracted_data = extract_investor_data_from_containers(investor_containers, existing_names)
        
        # Save the extracted data
        if extracted_data:
            try:
                save_data(extracted_data, OUTPUT_FILENAME, append_mode=RESUME_FROM_CSV)
                print(f"✅ Saved {len(extracted_data)} investors to CSV file")
            except Exception as e:
                print(f"❌ Error saving data: {e}")
        else:
            print("⚠️  No new investors found to save")
            
        return extracted_data

    print("Parsing final HTML...")
    soup = BeautifulSoup(page.content(), 'html.parser')
    
    # Debug: Let's see what elements we can find
    print("Debug: Looking for investor-related elements...")
    
    # Try different selectors for PIF portfolio structure
    selectors_to_try = [
        "ul.search-result-list li",  # Direct li elements (PRIORITY)
        "div.component.search-results.search-results-container.grid-view.col-12.initialized",  # Main container
        "ul.search-result-list",  # List of investors
        "li",  # Individual investor items
        "div.grid-container",  # Grid container for investor cards
        "div[class*='search-result']",  # Any search result elements
        "div[class*='grid']",  # Any grid elements
        "div[class*='card']",  # Any card elements
        "article",  # Article elements
        "div[class*='investor']"  # Any investor-related elements
    ]
    
    investor_containers = []
    for selector in selectors_to_try:
        elements = soup.select(selector)
        print(f"Selector '{selector}': Found {len(elements)} elements")
        if elements and len(elements) > len(investor_containers):
            investor_containers = elements
            print(f"Using selector: {selector} (found {len(elements)} elements)")
    
    # If we found li elements directly, use them instead of containers
    if investor_containers and investor_containers[0].name == 'li':
        print(f"Found {len(investor_containers)} li elements directly - using these for extraction")
        data = extract_investor_data_from_li_elements(investor_containers, existing_names)
    else:
        # Extract investor data from containers
        data = extract_investor_data_from_containers(investor_containers, existing_names)
    
    return data

def extract_investor_data_from_li_elements(li_elements, existing_names=None):
    """Extract investor data directly from li elements"""
    global scraped_data, stop_scraping
    
    print(f"🔍 Extracting investor data from {len(li_elements)} li elements...")
    
    all_investors = []
    seen_names = set()  # Track names to avoid duplicates
    
    # Extract data from each li element
    for li in li_elements:
        if stop_scraping:
            break
            
        # Extract profile link (first href in li)
        profile_link = "N/A"
        first_link = li.select_one("a")
        if first_link and first_link.has_attr('href'):
            href = first_link['href']
            # Convert relative URL to absolute URL
            if href.startswith('/'):
                profile_link = f"https://www.pif.gov.sa{href}"
            else:
                profile_link = href
        
        # Extract title (h5 from div.text-wrapper-investment-type)
        title = "N/A"
        title_element = li.select_one("div.text-wrapper-investment-type h5")
        if not title_element:
            # Try alternative selectors for title
            title_element = li.select_one("h5")
        if title_element:
            title = title_element.text.strip()
        
        # Extract name (h4 from div.text-wrapper)
        name = "N/A"
        name_element = li.select_one("div.text-wrapper h4")
        if not name_element:
            # Try alternative selectors for name
            name_element = li.select_one("h4")
        if name_element:
            name = name_element.text.strip()
        
        # Skip if no meaningful data found
        if name == "N/A" and title == "N/A" and profile_link == "N/A":
            continue
        
        # Skip if we've already seen this name in this run
        if name in seen_names:
            continue
            
        # Skip if already in existing CSV
        if existing_names and name in existing_names:
            continue
            
        seen_names.add(name)
        
        # Stop if we've reached the limit
        if MAX_INVESTORS > 0 and len(all_investors) >= MAX_INVESTORS:
            break
        
        row = {
            "Name": name,
            "Title": title,
            "Profile Link": profile_link,
            "Website": "N/A",
            "Social Links": "N/A"
        }
        all_investors.append(row)
        scraped_data.append(row)  # Add to global data for interrupt handling
    
    print(f"📊 Found {len(all_investors)} new investors (skipped {len(seen_names) - len(all_investors)} existing)")
    
    if not all_investors:
        print("❌ No new investors found. All investors on page are already in CSV.")
        return []
    
    return all_investors

def extract_profile_data(page, profile_url):
    """Extract website and social media links from investor profile page"""
    global stop_scraping
    
    if stop_scraping:
        return {"Website": "N/A", "Social Links": "N/A"}
    
    try:
        print(f"🔗 Visiting profile: {profile_url}")
        
        # Navigate to the profile page
        page.goto(profile_url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_load_state("domcontentloaded", timeout=15000)
        
        # Parse the page content
        soup = BeautifulSoup(page.content(), 'html.parser')
        
        # Extract website link
        website = "N/A"
        website_element = soup.select_one("div.company-wrapper div.field-website a.primary-btn")
        if website_element and website_element.has_attr('href'):
            website = website_element['href']
            if website.startswith('/'):
                website = f"https://www.pif.gov.sa{website}"
        
        # Extract social media links
        social_links = []
        social_elements = soup.select("div.social-wrapper div.social-media-list a")
        
        # If no social elements found, try alternative selector
        if not social_elements:
            social_elements = soup.select("div.social-media-block a")
            # Filter out the website link from social media links
            for social_element in social_elements:
                if social_element.has_attr('href'):
                    href = social_element['href']
                    # Skip if this is the website link (already extracted above)
                    if href == website:
                        continue
                    if href.startswith('/'):
                        href = f"https://www.pif.gov.sa{href}"
                    social_links.append(href)
        else:
            for social_element in social_elements:
                if social_element.has_attr('href'):
                    href = social_element['href']
                    if href.startswith('/'):
                        href = f"https://www.pif.gov.sa{href}"
                    social_links.append(href)
        
        social_links_str = "; ".join(social_links) if social_links else "N/A"
        
        print(f"  📊 Website: {website}")
        print(f"  📊 Social Links: {len(social_links)} found")
        
        return {
            "Website": website,
            "Social Links": social_links_str
        }
        
    except Exception as e:
        print(f"  ❌ Error extracting profile data: {str(e)}")
        return {"Website": "N/A", "Social Links": "N/A"}

def extract_all_profile_data(page, investors_data):
    """Extract website and social media data from all investor profiles"""
    global stop_scraping
    
    print(f"\n🔗 Starting profile data extraction for {len(investors_data)} investors...")
    
    for i, investor in enumerate(investors_data, 1):
        if stop_scraping:
            print("🛑 Profile extraction stopped by user")
            break
        
        profile_link = investor.get('Profile Link', 'N/A')
        investor_name = investor.get('Name', 'Unknown')
        
        if profile_link == 'N/A' or not profile_link.startswith('http'):
            print(f"⚠️  [{i}/{len(investors_data)}] Skipping {investor_name} - no valid profile link")
            continue
        
        print(f"\n📄 [{i}/{len(investors_data)}] Extracting profile data for {investor_name}...")
        
        # Extract profile data
        profile_data = extract_profile_data(page, profile_link)
        
        # Update the investor data
        investor['Website'] = profile_data['Website']
        investor['Social Links'] = profile_data['Social Links']
        
        # Add a small delay to be respectful to the server
        page.wait_for_timeout(1000)
    
    print(f"\n✅ Profile data extraction completed!")
    return investors_data

def extract_investor_data_from_containers(containers, existing_names=None):
    """Extract investor data from PIF portfolio containers"""
    global scraped_data, stop_scraping
    
    print(f"🔍 Extracting investor data from {len(containers)} containers...")
    
    all_investors = []
    seen_names = set()  # Track names to avoid duplicates
    
    # First, try to find li elements directly from all containers (PRIORITY)
    all_li_elements = []
    for container in containers:
        if stop_scraping:
            break
        li_elements = container.select("ul.search-result-list li")
        if li_elements:
            all_li_elements.extend(li_elements)
    
    if all_li_elements:
        print(f"Found {len(all_li_elements)} li elements total - using these for extraction")
        investor_cards = all_li_elements
    else:
        # Fallback: look for grid-container elements
        print("No li elements found, falling back to grid-container elements")
        investor_cards = []
        for container in containers:
            if stop_scraping:
                break
            grid_containers = container.select("div.grid-container")
            if grid_containers:
                investor_cards.extend(grid_containers)
                print(f"Found {len(grid_containers)} grid-container elements")
        
        # If still no cards, look for any divs that might contain investor data
        if not investor_cards:
            for container in containers:
                if stop_scraping:
                    break
                potential_cards = container.select("div")
                # Filter for divs that might contain investor information
                for div in potential_cards:
                    # Look for divs that have h4 or h5 tags (name/title indicators)
                    if div.select_one("h4") or div.select_one("h5"):
                        investor_cards.append(div)
            print(f"Found {len(investor_cards)} potential investor cards in divs")
    
    # Extract data from each investor card
    for card in investor_cards:
        if stop_scraping:
            break
            
        # Extract profile link (first href in li)
        profile_link = "N/A"
        if card.name == 'li':
            # Look for first href in the li element
            first_link = card.select_one("a")
            if first_link and first_link.has_attr('href'):
                href = first_link['href']
                # Convert relative URL to absolute URL
                if href.startswith('/'):
                    profile_link = f"https://www.pif.gov.sa{href}"
                else:
                    profile_link = href
        else:
            # Look for any link in the card
            link_element = card.select_one("a")
            if link_element and link_element.has_attr('href'):
                href = link_element['href']
                # Convert relative URL to absolute URL
                if href.startswith('/'):
                    profile_link = f"https://www.pif.gov.sa{href}"
                else:
                    profile_link = href
        
        # Extract title (h5 from div.text-wrapper-investment-type)
        title = "N/A"
        title_element = card.select_one("div.text-wrapper-investment-type h5")
        if not title_element:
            # Try alternative selectors for title
            title_element = card.select_one("h5")
        if title_element:
            title = title_element.text.strip()
        
        # Extract name (h4 from div.text-wrapper)
        name = "N/A"
        name_element = card.select_one("div.text-wrapper h4")
        if not name_element:
            # Try alternative selectors for name
            name_element = card.select_one("h4")
        if name_element:
            name = name_element.text.strip()
        
        # Skip if no meaningful data found
        if name == "N/A" and title == "N/A" and profile_link == "N/A":
            continue
        
        # Skip if we've already seen this name in this run
        if name in seen_names:
            continue
            
        # Skip if already in existing CSV
        if existing_names and name in existing_names:
            continue
            
        seen_names.add(name)
        
        # Stop if we've reached the limit
        if MAX_INVESTORS > 0 and len(all_investors) >= MAX_INVESTORS:
            break
        
        row = {
            "Name": name,
            "Title": title,
            "Profile Link": profile_link,
            "Website": "N/A",
            "Social Links": "N/A"
        }
        all_investors.append(row)
        scraped_data.append(row)  # Add to global data for interrupt handling
    
    print(f"📊 Found {len(all_investors)} new investors (skipped {len(seen_names) - len(all_investors)} existing)")
    
    if not all_investors:
        print("❌ No new investors found. All investors on page are already in CSV.")
        return []
    
    return all_investors

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
        print(f"✅ {len(data)} new investors added to existing CSV file {csv_path}")
        print(f"📊 Total investors in CSV: {len(combined_df)}")
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
    
    print("--- PIF Investors Scraper (v1 - Background Mode) ---")
    print("🔒 Using Chromium browser with Playwright")
    print(f"🎯 Target URL: {URL}")
    if MAX_INVESTORS > 0:
        print(f"📊 Investor Limit: {MAX_INVESTORS} investors")
    else:
        print("📊 Investor Limit: No limit (collect all)")
    
    if RESUME_FROM_CSV:
        print("🔄 Resume Mode: Will continue from last investor in CSV")
    else:
        print("🔄 Fresh Start: Will start from beginning")
    
    if RUN_IN_BACKGROUND:
        print("🖥️  Background Mode: Running without browser window (faster)")
    else:
        print("🖥️  Visible Mode: Browser window will be shown")
    
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
        
        print("🎯 Navigating to PIF portfolio page...")
        result_data = scrape_pif_investors(page, URL, existing_names)
        
        # Check if scraping was stopped early
        if stop_scraping:
            if result_data:
                print(f"🎉 Scraping stopped by user! Found {len(result_data)} new investors.")
                
                # Extract profile data (website and social links)
                print(f"\n🔗 Extracting profile data from {len(result_data)} investors...")
                result_data_with_profiles = extract_all_profile_data(page, result_data)
                
                print(f"💾 Saving data...")
                save_data(result_data_with_profiles, OUTPUT_FILENAME, append_mode=RESUME_FROM_CSV)
            else:
                print("❌ Scraping stopped by user, but no new data was found.")
        else:
            # Continue with pagination if not stopped
            print("\n🔄 Starting pagination to scrape additional pages (pages 2-7)...")
            pagination_data = scrape_pif_investors_pagination(page, URL, existing_names, start_page=2, end_page=7)
            
            # Combine all data
            all_data = result_data + pagination_data
            
            if all_data:
                print(f"\n🎉 Scraping finished! Found {len(all_data)} total new investors.")
                
                # Extract profile data from all investors
                print(f"\n🔗 Extracting profile data from {len(all_data)} investors...")
                all_data_with_profiles = extract_all_profile_data(page, all_data)
                
                print(f"\n💾 Saving all data...")
                save_data(all_data_with_profiles, OUTPUT_FILENAME, append_mode=RESUME_FROM_CSV)
            else:
                print("❌ No new data was scraped from any page.")
    
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
