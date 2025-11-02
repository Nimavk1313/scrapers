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
URL = "https://www.re-create.com/mentors/?"
OUTPUT_FILENAME = "recreate_mentors"

# <<<<<<< MENTOR LIMIT CONFIGURATION >>>>>>>
# Set the maximum number of mentors to collect (0 = no limit)
MAX_MENTORS = 5000  # Change this to limit mentors (e.g., 50, 100, 200)

# <<<<<<< RESUME FEATURE CONFIGURATION >>>>>>>
# Set to True to resume from last mentor in existing CSV file
RESUME_FROM_CSV = True  # Set to False to start fresh

# <<<<<<< SPEED CONFIGURATION >>>>>>>
# Set to True to skip portfolio extraction for maximum speed
SKIP_PORTFOLIO_EXTRACTION = False  # Set to True for faster scraping

# <<<<<<< BACKGROUND MODE CONFIGURATION >>>>>>>
# Set to True to run in background (no browser window)
RUN_IN_BACKGROUND = True  # Set to False to see browser window

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
        
        browser = playwright.chromium.launch_persistent_context(
            user_data_dir="/Users/Nomercya/Library/Application Support/Google/Chrome",
            headless=RUN_IN_BACKGROUND,  # Use background mode setting
            args=browser_args,
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
        )
        
        print("✅ Playwright initialized with Chromium!")
        
        # Get the first page (or create a new one)
        page = browser.pages[0] if browser.pages else browser.new_page()
        
        # Set timeouts - reduced for speed
        page.set_default_timeout(15000)  # 15 seconds
        page.set_default_navigation_timeout(15000)
        
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
        print(f"📄 Found existing CSV with {total_existing} mentors")
        print(f"🔄 Will skip any mentors already in CSV")
        
        return existing_names
        
    except Exception as e:
        print(f"⚠️  Error reading existing CSV: {e}")
        print("📄 Starting fresh.")
        return set()

def extract_portfolio_links(page, mentors_data):
    """Extract portfolio links from mentor profile pages"""
    global stop_scraping
    
    print(f"\n🔗 Extracting portfolio links from {len(mentors_data)} mentor profiles...")
    
    for i, mentor in enumerate(mentors_data, 1):
        if stop_scraping:
            print("🛑 Portfolio extraction stopped by user")
            break
            
        profile_link = mentor.get('Profile Link', 'N/A')
        mentor_name = mentor.get('Name', 'Unknown')
        
        if profile_link == 'N/A' or not profile_link.startswith('http'):
            print(f"⚠️  Skipping {mentor_name} - no valid profile link")
            mentor['Portfolio Link'] = 'N/A'
            continue
            
        print(f"\n📄 [{i}/{len(mentors_data)}] Extracting portfolio for {mentor_name}...")
        print(f"🔗 Visiting: {profile_link}")
        
        try:
            # Navigate to mentor profile page - optimized for speed
            page.goto(profile_link, wait_until="domcontentloaded")
            page.wait_for_load_state("networkidle", timeout=8000)  # Reduced from 30000
            
            # Wait for page to load - reduced for speed
            page.wait_for_timeout(1000)  # Reduced from 3000
            
            # Parse the page
            soup = BeautifulSoup(page.content(), 'html.parser')
            
            # Look for portfolio link in the specified structure
            portfolio_link = "N/A"
            
            # Try the exact selector path: div.mentor-skills > ul.list-bullets > a.link-mentor-portfolio
            portfolio_element = soup.select_one("div.mentor-skills ul.list-bullets a.link-mentor-portfolio")
            
            if portfolio_element and portfolio_element.has_attr('href'):
                portfolio_link = portfolio_element['href']
                print(f"✅ Found portfolio link: {portfolio_link}")
            else:
                # Try alternative selectors if the exact one doesn't work
                alternative_selectors = [
                    "div.mentor-skills a.link-mentor-portfolio",
                    "div.mentor-skills a[href*='portfolio']",
                    "div.mentor-skills a[href*='behance']",
                    "div.mentor-skills a[href*='dribbble']",
                    "div.mentor-skills a[href*='github']",
                    "div.mentor-skills a[href*='linkedin']",
                    "a.link-mentor-portfolio",
                    "a[href*='portfolio']"
                ]
                
                for selector in alternative_selectors:
                    portfolio_element = soup.select_one(selector)
                    if portfolio_element and portfolio_element.has_attr('href'):
                        portfolio_link = portfolio_element['href']
                        print(f"✅ Found portfolio link (alternative selector): {portfolio_link}")
                        break
                
                if portfolio_link == "N/A":
                    print(f"⚠️  No portfolio link found for {mentor_name}")
            
            # Add portfolio link to mentor data
            mentor['Portfolio Link'] = portfolio_link
            
        except Exception as e:
            print(f"❌ Error extracting portfolio for {mentor_name}: {e}")
            mentor['Portfolio Link'] = 'N/A'
            continue
    
    print(f"\n✅ Portfolio extraction completed for {len(mentors_data)} mentors")
    return mentors_data

def scrape_recreate_mentors_pagination(page, base_url, existing_names=None, start_page=2, end_page=30):
    """Scrape mentors from multiple pages using pagination"""
    global scraped_data, stop_scraping
    
    print(f"🔄 Starting pagination scraping from page {start_page} to {end_page}")
    
    all_mentors_data = []
    
    for page_num in range(start_page, end_page + 1):
        if stop_scraping:
            print("🛑 Pagination stopped by user")
            break
            
        # Handle URL construction properly
        if '?' in base_url:
            page_url = f"{base_url}&results={page_num}"
        else:
            page_url = f"{base_url}?results={page_num}"
        print(f"\n📄 Scraping page {page_num}: {page_url}")
        
        try:
            # Navigate to the page - optimized for speed
            page.goto(page_url, wait_until="domcontentloaded")
            page.wait_for_load_state("networkidle", timeout=8000)  # Reduced from 30000
            
            # Wait for content to load - reduced for speed
            page.wait_for_timeout(1000)  # Reduced from 3000
            
            # Parse the page
            soup = BeautifulSoup(page.content(), 'html.parser')
            
            # Find mentor cards using the same logic as the main function
            mentor_cards = soup.select("a.mentor-card")
            
            if not mentor_cards:
                print(f"⚠️  No mentor cards found on page {page_num}")
                continue
                
            print(f"📊 Found {len(mentor_cards)} mentor cards on page {page_num}")
            
            # Filter out existing mentors
            new_mentors = []
            seen_names = set()
            
            for card in mentor_cards:
                # Get name
                name_element = card.select_one("div.mentor-card__link h2")
                if name_element:
                    mentor_name = name_element.text.strip()
                    
                    # Skip if already seen in this run or in existing CSV
                    if mentor_name in seen_names or (existing_names and mentor_name in existing_names):
                        continue
                        
                    seen_names.add(mentor_name)
                    new_mentors.append(card)
            
            print(f"📊 Found {len(new_mentors)} new mentors on page {page_num}")
            
            # Extract data from new mentors
            page_mentors_data = []
            for card in new_mentors:
                # Get profile link
                profile_link = card['href'] if card.has_attr('href') else "N/A"
                
                # Get name
                name_element = card.select_one("div.mentor-card__link h2")
                name = name_element.text.strip() if name_element else "N/A"
                
                # Get location
                location_element = card.select_one("div.mentor-card__link p.strapline_small")
                location = location_element.text.strip() if location_element else "N/A"
                
                # Get job title
                job_title_element = card.select_one("div.mentor-card__link p.badge-role")
                job_title = job_title_element.text.strip() if job_title_element else "N/A"
                
                # Get description
                description_element = card.select_one("div.mentor-card__link p.para.three-lines.ddd-truncated")
                if not description_element:
                    description_element = (card.select_one("div.mentor-card__link p.para") or 
                                         card.select_one("div.mentor-card__link p[class*='para']"))
                description = description_element.text.strip() if description_element else "N/A"
                
                row = {
                    "Name": name,
                    "Profile Link": profile_link,
                    "Location": location,
                    "Job Title": job_title,
                    "Description": description,
                    "Portfolio Link": "N/A"  # Will be filled later by portfolio extraction
                }
                page_mentors_data.append(row)
                scraped_data.append(row)  # Add to global data
            
            all_mentors_data.extend(page_mentors_data)
            
            if page_mentors_data:
                print(f"✅ Extracted {len(page_mentors_data)} mentors from page {page_num}")
            else:
                print(f"⚠️  No new mentors found on page {page_num}")
                
        except Exception as e:
            print(f"❌ Error scraping page {page_num}: {e}")
            continue
    
    print(f"\n🎉 Pagination completed! Total new mentors found: {len(all_mentors_data)}")
    return all_mentors_data

def scrape_recreate_mentors(page, url, existing_names=None):
    """Estekhraj-e etela'at az site-e Re-Create using Playwright"""
    global scraped_data, stop_scraping
    
    print(f"🚀 Loading Re-Create mentors page: {url}")
    
    if existing_names:
        print(f"🔄 Will skip {len(existing_names)} existing mentors")
    
    # Clear scraped data at start
    scraped_data = []
    stop_scraping = False
    
    # Navigate to the URL with Playwright
    try:
        print("📍 Navigating to Re-Create mentors page...")
        page.goto(url, wait_until="domcontentloaded")
        
        # Wait for page to load - reduced timeout for speed
        page.wait_for_load_state("networkidle", timeout=10000)
        
        current_url = page.url
        page_title = page.title()
        
        print(f"✅ Page loaded successfully!")
        print(f"📍 Current URL: {current_url}")
        print(f"📄 Page Title: {page_title}")
        
        # Verify we're on Re-Create
        if "re-create.com" in current_url:
            print("✅ Confirmed: On Re-Create website!")
        else:
            print(f"⚠️  Warning: Not on Re-Create page. Current URL: {current_url}")
            
    except Exception as e:
        print(f"❌ Error loading Re-Create: {e}")
        raise Exception(f"Failed to load Re-Create: {e}")
    
    # Additional wait to ensure page is fully loaded - reduced for speed
    print("⏳ Waiting for page to fully load...")
    page.wait_for_timeout(2000)  # Wait 2 seconds
    
    # Check if we need to login
    try:
        # Look for login indicators
        login_elements = page.locator("//a[contains(text(), 'Login') or contains(text(), 'Sign in')]")
        if login_elements.count() > 0:
            print("⚠️  Login required! Please log in to Re-Create in your Chrome browser first.")
            print("After logging in, close Chrome completely and run this script again.")
            return []
        else:
            print("✅ Already logged in or no login required!")
    except Exception as e:
        print(f"Could not check login status: {e}")
    
    # Check page content
    try:
        page_content = page.content()
        if "mentor" in page_content.lower() or "re-create" in page_content.lower():
            print("✅ Page content looks correct - found mentor/re-create keywords")
        else:
            print("⚠️  Page content might not be loading correctly")
            print("Page content length:", len(page_content))
    except Exception as e:
        print(f"Could not check page content: {e}")

    print("Starting to extract mentors from Re-Create page...")
    if MAX_MENTORS > 0:
        print(f"🎯 Target: Collecting {MAX_MENTORS} NEW mentors (skipping existing ones)")
    else:
        print("🎯 Target: Collecting all available NEW mentors")
    
    # For Re-Create, we'll scroll to load more content instead of clicking buttons
    print("Scrolling to load all mentors...")
    
    # Scroll down to load all mentors - optimized for speed
    last_height = page.evaluate("document.body.scrollHeight")
    scroll_attempts = 0
    max_scroll_attempts = 10  # Reduced from 20
    
    while scroll_attempts < max_scroll_attempts and not stop_scraping:
        # Check if user wants to stop
        if stop_scraping:
            print("🛑 Stop signal received! Saving progress...")
            break
            
        # Scroll down
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(1500)  # Reduced from 3000ms
        
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
        
        # Extract mentors that are currently visible on the page
        print("Parsing current HTML...")
        soup = BeautifulSoup(page.content(), 'html.parser')
        
        # Debug: Let's see what elements we can find
        print("Debug: Looking for mentor-related elements...")
        
        # Try different selectors - prioritize a.mentor-card elements
        selectors_to_try = [
            "a.mentor-card",  # Direct mentor card links - this is what we want
            "a[href*='/mentors/']",  # 15 elements - mentor profile links
            "div:has(h2)",  # 11 elements - divs with mentor names
            "div:has(p.strapline_small)",  # 11 elements - divs with locations
            "div[class*='mentor']",  # 20 elements - divs with mentor in class
            "div.mentor-cards",
            ".mentor-card", 
            "article",
            ".card",
            "[data-mentor]",
            "div[class*='card']"
        ]
        
        mentor_cards = []
        for selector in selectors_to_try:
            elements = soup.select(selector)
            print(f"Selector '{selector}': Found {len(elements)} elements")
            # Prioritize a.mentor-card selector
            if selector == "a.mentor-card" and elements:
                mentor_cards = elements
                print(f"Using selector: {selector} (found {len(elements)} elements)")
                break
            elif elements and len(elements) > len(mentor_cards):
                mentor_cards = elements
                print(f"Using selector: {selector} (found {len(elements)} elements)")
        
        # Filter out elements that don't look like mentor cards
        filtered_cards = []
        for card in mentor_cards:
            # Skip body, html, and other top-level elements
            if card.name in ['body', 'html', 'head']:
                continue
                
            # Skip if it's a link to sendowl or other non-mentor pages
            if card.name == 'a' and card.has_attr('href'):
                href = card['href']
                if 'sendowl' in href or 'transactions' in href or href == 'https://www.re-create.com':
                    continue
            
            # Must have either a name (h2) or be a mentor profile link
            has_name = card.select_one("h2") is not None
            is_mentor_link = card.name == 'a' and card.has_attr('href') and '/mentors/' in card['href']
            
            if has_name or is_mentor_link:
                filtered_cards.append(card)
        
        mentor_cards = filtered_cards
        print(f"After filtering: {len(mentor_cards)} mentor cards")
        
        print(f"Found {len(mentor_cards)} mentor cards. Extracting data...")
        
        # Filter out existing mentors and apply limit
        new_mentors = []
        seen_names = set()  # Track names to avoid duplicates
        
        for card in mentor_cards:
            # Try to find name in different ways depending on element type
            name_element = None
            mentor_name = None
            
            if card.name == 'a':
                # If it's a mentor-card link, look for h2 in the mentor-card__link div
                name_element = card.select_one("div.mentor-card__link h2")
                if not name_element:
                    # Fallback: look for h2 anywhere in the link
                    name_element = card.select_one("h2")
            else:
                # If it's a div, look for h2 inside it
                name_element = card.select_one("h2")
            
                if name_element:
                    mentor_name = name_element.text.strip()
                
                # Skip if we've already seen this name in this run
                if mentor_name in seen_names:
                    continue
                    
                # Skip if already in existing CSV
                if existing_names and mentor_name in existing_names:
                    continue
                    
                seen_names.add(mentor_name)
                new_mentors.append(card)
                
                # Stop if we've reached the limit
                if MAX_MENTORS > 0 and len(new_mentors) >= MAX_MENTORS:
                    break
        
        print(f"📊 Found {len(new_mentors)} new mentors to save (skipped {len(mentor_cards) - len(new_mentors)} existing)")
        
        # Extract data from new mentors
        extracted_data = []
        for i, card in enumerate(new_mentors, 1):
            # Get profile link - simplified logic for mentor-card elements
            profile_link = "N/A"
            
            # Since we're using a.mentor-card selector, the href should be the profile link
            if card.name == 'a' and card.has_attr('href'):
                profile_link = card['href']
            else:
                # Look for mentor profile link within the element
                profile_link_element = card.select_one("a[href*='/mentors/']")
            if profile_link_element and profile_link_element.has_attr('href'):
                profile_link = profile_link_element['href']
            
            # Get name - look in mentor-card__link div
            name = "N/A"
            if card.name == 'a':
                name_element = card.select_one("div.mentor-card__link h2")
            else:
                name_element = card.select_one("h2")
            
            if name_element:
                name = name_element.text.strip()
            
            # Get location - look in mentor-card__link div
            location = "N/A"
            if card.name == 'a':
                location_element = card.select_one("div.mentor-card__link p.strapline_small")
            else:
                location_element = card.select_one("p.strapline_small")
            
            if location_element:
                location = location_element.text.strip()
            
            # Get job title - look in mentor-card__link div
            job_title = "N/A"
            if card.name == 'a':
                job_title_element = card.select_one("div.mentor-card__link p.badge-role")
            else:
                job_title_element = card.select_one("p.badge-role")
            
            if job_title_element:
                job_title = job_title_element.text.strip()
            
            # Get description - look in mentor-card__link div
            description = "N/A"
            if card.name == 'a':
                description_element = card.select_one("div.mentor-card__link p.para.three-lines.ddd-truncated")
                if not description_element:
                    # Try alternative selectors
                    description_element = (card.select_one("div.mentor-card__link p.para") or 
                                         card.select_one("div.mentor-card__link p[class*='para']"))
            else:
                description_element = card.select_one("p.para.three-lines.ddd-truncated")
                if not description_element:
                    description_element = (card.select_one("p.para") or 
                                         card.select_one("p[class*='para']"))
            
            if description_element:
                description = description_element.text.strip()
            
            row = {
                "Name": name,
                "Profile Link": profile_link,
                "Location": location,
                "Job Title": job_title,
                "Description": description,
                "Portfolio Link": "N/A"  # Will be filled later by portfolio extraction
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

    print("Parsing final HTML...")
    soup = BeautifulSoup(page.content(), 'html.parser')
    
    # Debug: Let's see what elements we can find
    print("Debug: Looking for mentor-related elements...")
    
    # Try different selectors - prioritize a.mentor-card elements
    selectors_to_try = [
        "a.mentor-card",  # Direct mentor card links - this is what we want
        "a[href*='/mentors/']",  # 15 elements - mentor profile links
        "div:has(h2)",  # 11 elements - divs with mentor names
        "div:has(p.strapline_small)",  # 11 elements - divs with locations
        "div[class*='mentor']",  # 20 elements - divs with mentor in class
        "div.mentor-cards",
        ".mentor-card", 
        "article",
        ".card",
        "[data-mentor]",
        "div[class*='card']"
    ]
    
    mentor_cards = []
    for selector in selectors_to_try:
        elements = soup.select(selector)
        print(f"Selector '{selector}': Found {len(elements)} elements")
        # Prioritize a.mentor-card selector
        if selector == "a.mentor-card" and elements:
            mentor_cards = elements
            print(f"Using selector: {selector} (found {len(elements)} elements)")
            break
        elif elements and len(elements) > len(mentor_cards):
            mentor_cards = elements
            print(f"Using selector: {selector} (found {len(elements)} elements)")
    
    # Filter out elements that don't look like mentor cards
    filtered_cards = []
    for card in mentor_cards:
        # Skip body, html, and other top-level elements
        if card.name in ['body', 'html', 'head']:
            continue
            
        # Skip if it's a link to sendowl or other non-mentor pages
        if card.name == 'a' and card.has_attr('href'):
            href = card['href']
            if 'sendowl' in href or 'transactions' in href or href == 'https://www.re-create.com':
                continue
        
        # Must have either a name (h2) or be a mentor profile link
        has_name = card.select_one("h2") is not None
        is_mentor_link = card.name == 'a' and card.has_attr('href') and '/mentors/' in card['href']
        
        if has_name or is_mentor_link:
            filtered_cards.append(card)
    
    mentor_cards = filtered_cards
    print(f"After filtering: {len(mentor_cards)} mentor cards")
    
    data = []
    print(f"Found {len(mentor_cards)} mentor cards. Extracting data...")

    # Filter out existing mentors and apply limit
    new_mentors = []
    seen_names = set()  # Track names to avoid duplicates
    
    for card in mentor_cards:
        # Try to find name in different ways depending on element type
        name_element = None
        mentor_name = None
        
        if card.name == 'a':
            # If it's a mentor-card link, look for h2 in the mentor-card__link div
            name_element = card.select_one("div.mentor-card__link h2")
            if not name_element:
                # Fallback: look for h2 anywhere in the link
                name_element = card.select_one("h2")
        else:
            # If it's a div, look for h2 inside it
            name_element = card.select_one("h2")
        
            if name_element:
                mentor_name = name_element.text.strip()
            
            # Skip if we've already seen this name in this run
            if mentor_name in seen_names:
                continue
                
            # Skip if already in existing CSV
            if existing_names and mentor_name in existing_names:
                continue
                
            seen_names.add(mentor_name)
            new_mentors.append(card)
            
            # Stop if we've reached the limit
            if MAX_MENTORS > 0 and len(new_mentors) >= MAX_MENTORS:
                break
    
    print(f"📊 Found {len(new_mentors)} new mentors (skipped {len(mentor_cards) - len(new_mentors)} existing)")
    
    if not new_mentors:
        print("❌ No new mentors found. All mentors on page are already in CSV.")
        return []

    for i, card in enumerate(new_mentors, 1):
        # Get profile link - simplified logic for mentor-card elements
        profile_link = "N/A"
        
        # Since we're using a.mentor-card selector, the href should be the profile link
        if card.name == 'a' and card.has_attr('href'):
            profile_link = card['href']
        else:
            # Look for mentor profile link within the element
            profile_link_element = card.select_one("a[href*='/mentors/']")
        if profile_link_element and profile_link_element.has_attr('href'):
            profile_link = profile_link_element['href']
        
        # Get name - look in mentor-card__link div
        name = "N/A"
        if card.name == 'a':
            name_element = card.select_one("div.mentor-card__link h2")
        else:
            name_element = card.select_one("h2")
        
        if name_element:
            name = name_element.text.strip()
        
        # Get location - look in mentor-card__link div
        location = "N/A"
        if card.name == 'a':
            location_element = card.select_one("div.mentor-card__link p.strapline_small")
        else:
            location_element = card.select_one("p.strapline_small")
        
        if location_element:
            location = location_element.text.strip()
        
        # Get job title - look in mentor-card__link div
        job_title = "N/A"
        if card.name == 'a':
            job_title_element = card.select_one("div.mentor-card__link p.badge-role")
        else:
            job_title_element = card.select_one("p.badge-role")
        
        if job_title_element:
            job_title = job_title_element.text.strip()
        
        # Get description - look in mentor-card__link div
        description = "N/A"
        if card.name == 'a':
            description_element = card.select_one("div.mentor-card__link p.para.three-lines.ddd-truncated")
            if not description_element:
                # Try alternative selectors
                description_element = (card.select_one("div.mentor-card__link p.para") or 
                                     card.select_one("div.mentor-card__link p[class*='para']"))
        else:
            description_element = card.select_one("p.para.three-lines.ddd-truncated")
            if not description_element:
                description_element = (card.select_one("p.para") or 
                                     card.select_one("p[class*='para']"))
        
        if description_element:
            description = description_element.text.strip()
        
        row = {
            "Name": name,
            "Profile Link": profile_link,
            "Location": location,
            "Job Title": job_title,
            "Description": description,
            "Portfolio Link": "N/A"  # Will be filled later by portfolio extraction
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
    
    print("--- Re-Create Mentors Scraper (v23 - Background Mode) ---")
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
    
    if SKIP_PORTFOLIO_EXTRACTION:
        print("⚡ Speed Mode: Portfolio extraction disabled for maximum speed")
    else:
        print("🔗 Portfolio Mode: Will extract portfolio links (slower but complete)")
    
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
        
        print("🎯 Navigating to Re-Create mentors page...")
        result_data = scrape_recreate_mentors(page, URL, existing_names)
        
        # Check if scraping was stopped early
        if stop_scraping:
            if result_data:
                print(f"🎉 Scraping stopped by user! Found {len(result_data)} new mentors.")
                
                # Extract portfolio links even if stopped early (if not skipped)
                if SKIP_PORTFOLIO_EXTRACTION:
                    print("⚡ Speed mode: Skipping portfolio extraction")
                    result_data_with_portfolios = result_data
                else:
                    result_data_with_portfolios = extract_portfolio_links(page, result_data)
                
                print(f"💾 Saving data...")
                save_data(result_data_with_portfolios, OUTPUT_FILENAME, append_mode=RESUME_FROM_CSV)
            else:
                print("❌ Scraping stopped by user, but no new data was found.")
        else:
            # Continue with pagination if not stopped
            print("\n🔄 Starting pagination to scrape additional pages...")
            pagination_data = scrape_recreate_mentors_pagination(page, URL, existing_names, start_page=2, end_page=30)
            
            # Combine all data
            all_data = result_data + pagination_data
            
            if all_data:
                print(f"\n🎉 Scraping finished! Found {len(all_data)} total new mentors.")
                
                # Extract portfolio links from all mentor profiles (if not skipped)
                if SKIP_PORTFOLIO_EXTRACTION:
                    print("⚡ Speed mode: Skipping portfolio extraction")
                    all_data_with_portfolios = all_data
                else:
                    all_data_with_portfolios = extract_portfolio_links(page, all_data)
                
                print(f"\n💾 Saving all data...")
                save_data(all_data_with_portfolios, OUTPUT_FILENAME, append_mode=RESUME_FROM_CSV)
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
