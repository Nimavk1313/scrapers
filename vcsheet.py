import time
import pandas as pd
import json
import os
import signal
import sys
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page
from bs4 import BeautifulSoup

# --- Configuration ---
URL = "https://www.vcsheet.com/investors"
OUTPUT_FILENAME = "vcsheet_investors"

# <<<<<<< INVESTOR LIMIT CONFIGURATION >>>>>>>
# Set the maximum number of investors to collect (0 = no limit)
MAX_INVESTORS = 100  # Change this to limit investors (e.g., 50, 100, 200)

# Credentials file path
CREDENTIALS_FILE = "dealroom_credentials.json"

# Global variable to store collected data
collected_investor_data = []

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
    """Handle login process for VC Sheet (no login required)"""
    print("✅ VC Sheet doesn't require login - proceeding with scraping")
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




def scrape_vcsheet(page, url):
    """Scrape investor data from VC Sheet using Playwright"""
    print(f"🚀 Loading VC Sheet: {url}")
    
    # Load existing investors to avoid duplicates
    existing_investors = load_existing_investors(OUTPUT_FILENAME)
    
    # Navigate to the URL with Playwright
    try:
        print("📍 Navigating to VC Sheet...")
        page.goto(url, wait_until="domcontentloaded")
        
        current_url = page.url
        page_title = page.title()
        
        print(f"✅ Page loaded successfully!")
        print(f"📍 Current URL: {current_url}")
        print(f"📄 Page Title: {page_title}")
        
        # Verify we're on VC Sheet
        if "vcsheet.com" in current_url:
            print("✅ Confirmed: On VC Sheet website!")
        else:
            print(f"⚠️  Warning: Not on VC Sheet page. Current URL: {current_url}")
            
    except Exception as e:
        print(f"❌ Error loading VC Sheet: {e}")
        raise Exception(f"Failed to load VC Sheet: {e}")
    
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
        if "list-item vert-list" in page_content.lower():
            print("✅ Page content looks correct - found investor cards")
        else:
            print("⚠️  Page content might not be loading correctly")
            print("Page content length:", len(page_content))
    except Exception as e:
        print(f"Could not check page content: {e}")

    print("🔄 Loading more investors...")
    if MAX_INVESTORS > 0:
        print(f"🎯 Target: Collecting up to {MAX_INVESTORS} investors")
    else:
        print("🎯 Target: Collecting all available investors")
    
    global collected_investor_data
    all_investor_data = []
    page_number = 1
    max_pages = 100  # Maximum pages to scrape
    
    while page_number <= max_pages:
        print(f"📄 Processing page {page_number}...")
        
        # Scroll and collect all investors on current page
        scroll_count = 0
        max_scrolls = 20  # Maximum scroll attempts per page
        
        while scroll_count < max_scrolls:
            # Extract data from all currently visible investors
            soup = BeautifulSoup(page.content(), 'html.parser')
            
            # Try multiple selectors for investor cards
            visible_cards = []
            card_selectors = [
                "div.list-item.vert-list.less-spacing.w-dyn-item",
                "div.list-item.vert-list.w-dyn-item",
                "div.list-item.w-dyn-item",
                "div.w-dyn-item",
                "div[class*='list-item']",
                "div[class*='investor']"
            ]
            
            for selector in card_selectors:
                cards = soup.select(selector)
                if cards:
                    visible_cards = cards
                    print(f"✅ Found {len(cards)} cards with selector: {selector}")
                    break
            
            if not visible_cards:
                print(f"❌ No investor cards found with any selector")
                # Debug: Print some HTML to see what's available
                all_divs = soup.select("div")
                print(f"🔍 Total divs on page: {len(all_divs)}")
                if all_divs:
                    print(f"🔍 First few div classes: {[div.get('class', []) for div in all_divs[:10]]}")
            
            print(f"📊 Page {page_number}, Scroll {scroll_count + 1}: Found {len(visible_cards)} investor cards")
            
            for card in visible_cards:
                try:
                    # Debug: Print card HTML structure
                    print(f"🔍 Card HTML: {str(card)[:200]}...")
                    
                    # Try multiple selectors for name extraction
                    name = "-"
                    name_selectors = [
                        "h3.list-heading.list-pages",
                        "h3.list-heading",
                        "h3",
                        ".list-heading",
                        "a h3",
                        "div h3"
                    ]
                    
                    for selector in name_selectors:
                        name_element = card.select_one(selector)
                        if name_element and name_element.text.strip():
                            name = name_element.text.strip()
                            print(f"✅ Found name with selector '{selector}': {name}")
                            break
                    
                    if name == "-":
                        print(f"❌ Could not find name in card")
                        continue
                    
                    # Check if we already have this investor in current session or existing CSV
                    if (not any(investor.get("Name") == name for investor in all_investor_data) and 
                        name not in existing_investors):
                        # Extract stages using the correct CSS selector path
                        stages = []
                        
                        # Use the correct selector path: div.ra-vert.more-space > div.align-row.center-mobile > div.pill-item
                        # Exclude invisible elements with w-condition-invisible class
                        stage_elements = card.select("div.ra-vert.more-space div.align-row.center-mobile div.pill-item:not(.w-condition-invisible)")
                        
                        if stage_elements:
                            for stage_element in stage_elements:
                                stage_text = stage_element.text.strip()
                                if stage_text and stage_text not in stages:
                                    stages.append(stage_text)
                        
                        # Join all found stages
                        stage = ", ".join(stages) if stages else "-"
                        
                        # Extract job title from div.html-embed.w-embed under div.align-row.sides
                        job_title = "-"
                        job_title_container = card.select_one("div.align-row.sides")
                        if job_title_container:
                            job_title_elements = job_title_container.select("div.html-embed.w-embed")
                            if job_title_elements:
                                job_title_texts = []
                                for element in job_title_elements:
                                    text = element.get_text(strip=True)
                                    if text:
                                        job_title_texts.append(text)
                                if job_title_texts:
                                    job_title = " ".join(job_title_texts)
                        
                        # Extract title from div.shortdesccard.more-top.w-richtext
                        title = "-"
                        title_element = card.select_one("div.shortdesccard.more-top.w-richtext")
                        if title_element:
                            title_text = title_element.get_text(strip=True)
                            if title_text:
                                title = title_text
                        
                        # Extract social links and categorize them
                        website = "-"
                        twitter = "-"
                        linkedin = "-"
                        youtube = "-"
                        crunchbase = "-"
                        email = "-"
                        other_links = []
                        
                        social_selectors = [
                            "div.align-row.right-align.center-mobile a",
                            "div[class*='right-align'] a",
                            "div[class*='social'] a"
                        ]
                        
                        for selector in social_selectors:
                            social_links_elements = card.select(selector)
                            if social_links_elements:
                                for link in social_links_elements:
                                    href = link.get('href', '')
                                    if href:
                                        # Check if there's a div inside the link for additional text
                                        div_inside = link.select_one("div")
                                        link_text = div_inside.text.strip() if div_inside else ""
                                        
                                        # Categorize the link based on URL or text
                                        href_lower = href.lower()
                                        text_lower = link_text.lower()
                                        
                                        if 'twitter.com' in href_lower or 'x.com' in href_lower or 'twitter' in text_lower:
                                            twitter = href
                                        elif 'linkedin.com' in href_lower or 'linkedin' in text_lower:
                                            linkedin = href
                                        elif 'youtube.com' in href_lower or 'youtu.be' in href_lower or 'youtube' in text_lower:
                                            youtube = href
                                        elif 'crunchbase.com' in href_lower or 'crunchbase' in text_lower:
                                            crunchbase = href
                                        elif 'mailto:' in href_lower or '@' in href_lower or 'email' in text_lower:
                                            email = href
                                        elif 'http' in href_lower and ('website' in text_lower or 'site' in text_lower or 'web' in text_lower):
                                            website = href
                                        else:
                                            # For other links, add them to other_links
                                            if href not in other_links:
                                                other_links.append(href)
                                break
                        
                        # Join other links
                        other_links_text = ", ".join(other_links) if other_links else "-"
                    
                        investor_data = {
                            "Name": name,
                            "Job Title": job_title,
                            "Title": title,
                            "Stage": stage,
                            "Website": website,
                            "Twitter": twitter,
                            "LinkedIn": linkedin,
                            "YouTube": youtube,
                            "Crunchbase": crunchbase,
                            "Email": email,
                            "Other Links": other_links_text
                        }
                        
                        all_investor_data.append(investor_data)
                        collected_investor_data.append(investor_data)  # Store in global variable
                        print(f"✅ Added: {name} (Stage: {stage})")
                    else:
                        if name in existing_investors:
                            print(f"⏭️ Skipped: {name} (already exists in CSV)")
                        else:
                            print(f"⏭️ Skipped: {name} (duplicate in current session)")
                        
                except Exception as e:
                    print(f"Error extracting investor data: {e}")
                    continue
            
            print(f"📊 Total unique investors collected: {len(all_investor_data)}")
            
            # Check if we've reached the limit
            if MAX_INVESTORS > 0 and len(all_investor_data) >= MAX_INVESTORS:
                print(f"✅ Reached target limit of {MAX_INVESTORS} investors!")
                return all_investor_data
            
            # Scroll down to load more content
            print("📜 Scrolling down...")
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(1000)  # Wait 1 second (faster)
            
            scroll_count += 1
        
        # Try to load more investors with retry mechanism
        print("🔄 Attempting to load more investors...")
        max_retry_attempts = 3
        new_investors_loaded = False
        
        for attempt in range(max_retry_attempts):
            try:
                if attempt == 0:
                    # First attempt: scroll to bottom completely
                    print("📜 Attempt 1: Scrolling to bottom of page...")
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    page.wait_for_timeout(2000)  # Wait 2 seconds for content to load
                else:
                    # Retry attempts: scroll up then down to bottom
                    print(f"📜 Attempt {attempt + 1}: Small scroll up then down to bottom...")
                    page.keyboard.press("PageUp")
                    page.wait_for_timeout(500)  # Quick wait
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    page.wait_for_timeout(2000)  # Wait 2 seconds for content to load
                
                # Check if new content loaded by comparing investor count
                soup_after_scroll = BeautifulSoup(page.content(), 'html.parser')
                new_cards = soup_after_scroll.select("div.list-item.vert-list.less-spacing.w-dyn-item")
                
                if len(new_cards) > len(visible_cards):
                    print(f"✅ Loaded more investors: {len(new_cards)} total cards found")
                    new_investors_loaded = True
                    page_number += 1
                    break
                else:
                    print(f"⏳ Attempt {attempt + 1}: No new investors loaded yet...")
                    
            except Exception as e:
                print(f"❌ Error during attempt {attempt + 1}: {e}")
                continue
        
        if not new_investors_loaded:
            print("✅ No more investors to load after all attempts - reached end of results")
            break
    
    print(f"🎉 Scraping completed! Collected {len(all_investor_data)} unique investors")
    return all_investor_data

def load_existing_investors(filename):
    """Load existing investors from CSV file to avoid duplicates"""
    csv_path = f"{filename}.csv"
    existing_investors = set()
    
    if os.path.exists(csv_path):
        try:
            df = pd.read_csv(csv_path)
            if 'Name' in df.columns:
                existing_investors = set(df['Name'].dropna().astype(str))
                print(f"📁 Loaded {len(existing_investors)} existing investors from {csv_path}")
            else:
                print(f"⚠️ CSV file exists but no 'Name' column found")
        except Exception as e:
            print(f"⚠️ Error loading existing CSV: {e}")
    else:
        print(f"📝 No existing CSV file found - will create new one")
    
    return existing_investors

def save_data(data, filename):
    """Save scraped data to CSV and JSON formats, appending to existing file"""
    if not data:
        print("No data found to save.")
        return

    csv_path = f"{filename}.csv"
    json_path = f"{filename}.json"
    
    # Check if CSV file already exists
    if os.path.exists(csv_path):
        try:
            # Load existing data
            existing_df = pd.read_csv(csv_path)
            print(f"📁 Found existing CSV with {len(existing_df)} investors")
            
            # Create new dataframe with new data
            new_df = pd.DataFrame(data)
            
            # Combine existing and new data
            combined_df = pd.concat([existing_df, new_df], ignore_index=True)
            
            # Remove duplicates based on Name column
            combined_df = combined_df.drop_duplicates(subset=['Name'], keep='first')
            
            # Save combined data
            combined_df.to_csv(csv_path, index=False, encoding='utf-8-sig')
            print(f"✅ Added {len(new_df)} new investors to existing CSV")
            print(f"📊 Total investors in CSV: {len(combined_df)}")
            
        except Exception as e:
            print(f"⚠️ Error appending to existing CSV: {e}")
            # Fallback: save new data only
            new_df = pd.DataFrame(data)
            new_df.to_csv(csv_path, index=False, encoding='utf-8-sig')
            print(f"✅ Data saved to new CSV file: {csv_path}")
    else:
        # No existing file, create new one
        df = pd.DataFrame(data)
        df.to_csv(csv_path, index=False, encoding='utf-8-sig')
        print(f"✅ New CSV file created: {csv_path}")

    # Save JSON (always overwrite for simplicity)
    df = pd.DataFrame(data)
    df.to_json(json_path, orient='records', indent=4, force_ascii=False)
    print(f"✅ Data successfully saved to {json_path}")

def save_partial_data():
    """Save any collected data when browser closes or script is interrupted"""
    global collected_investor_data
    if collected_investor_data:
        print("💾 Saving partial data before closing...")
        save_data(collected_investor_data, f"{OUTPUT_FILENAME}_partial")
        print(f"✅ Partial data saved: {len(collected_investor_data)} investors")
    else:
        print("📝 No data to save.")

def signal_handler(signum, frame):
    """Handle Ctrl+C and other interruption signals"""
    print("\n🛑 Script interrupted! Saving collected data...")
    save_partial_data()
    sys.exit(0)

def main():
    """Main function to run the VC Sheet scraper"""
    print("--- VC Sheet Investors Scraper ---")
    print("🔒 Using Chromium browser with Playwright")
    print(f"🎯 Target URL: {URL}")
    if MAX_INVESTORS > 0:
        print(f"📊 Investor Limit: {MAX_INVESTORS} investors")
    else:
        print("📊 Investor Limit: No limit (collect all)")
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
        
        print("🎯 Navigating to VC Sheet...")
        scraped_data = scrape_vcsheet(page, URL)
        
        if scraped_data:
            print(f"🎉 Scraping completed! Found {len(scraped_data)} investors.")
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
