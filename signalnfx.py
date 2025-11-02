import time
import pandas as pd
import json
import os
import signal
import sys
import random
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page
from bs4 import BeautifulSoup

# --- Configuration ---
URL = "https://signal.nfx.com/investor-lists/top-deeptech-seed-investors"
OUTPUT_FILENAME = "signal_nfx_investors"

# <<<<<<< INVESTOR LIMIT CONFIGURATION >>>>>>>
# Set the maximum number of investors to collect (0 = no limit)
MAX_INVESTORS = 1435  # Change this to limit investors (e.g., 50, 100, 200)

# Global variable to store collected data
collected_investor_data = []

# <<<<<<< 1. CHROME PROFILE CONFIGURATION >>>>>>>
# Your Chrome profile path (automatically configured based on your system)
# Profile Path: /Users/Nomercya/Library/Application Support/Google/Chrome/Profile 1


def extract_investor_profile_data(page, investor_url):
    """Extract additional data from individual investor profile page"""
    try:
        print(f"🔍 Extracting profile data from: {investor_url}")
        page.goto(investor_url, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)  # Wait for page to load
        
        # Add random delay to avoid being blocked
        delay = random.uniform(0.5, 1.5)
        print(f"⏳ Waiting {delay:.1f} seconds to avoid being blocked...")
        page.wait_for_timeout(int(delay * 1000))
        
        soup = BeautifulSoup(page.content(), 'html.parser')
        
        # Extract type from div.col-sm-6.col-xs-12 > div.relative.identity-block > div.subheader.white-subheader.b.pb1 > span
        investor_type = "-"
        try:
            type_container = soup.select_one("div.col-sm-6.col-xs-12 div.relative.identity-block div.subheader.white-subheader.b.pb1")
            if type_container:
                type_spans = type_container.select("span")
                type_texts = [span.get_text(strip=True) for span in type_spans if span.get_text(strip=True)]
                investor_type = ", ".join(type_texts) if type_texts else "-"
        except Exception as e:
            print(f"Error extracting type: {e}")
        
        # Extract job title from div.col-sm-6.col-xs-12 > div.subheader.lower-subheader.pb2
        job_title = "-"
        try:
            job_title_element = soup.select_one("div.col-sm-6.col-xs-12 div.subheader.lower-subheader.pb2")
            if job_title_element:
                job_title = job_title_element.get_text(strip=True)
        except Exception as e:
            print(f"Error extracting job title: {e}")
        
        # Extract social link from a.ml1.subheader.lower-subheader
        social_link = "-"
        try:
            social_element = soup.select_one("a.ml1.subheader.lower-subheader")
            if social_element:
                social_link = social_element.get('href', '').strip()
                if social_link and not social_link.startswith('http'):
                    if social_link.startswith('/'):
                        social_link = f"https://signal.nfx.com{social_link}"
                    else:
                        social_link = f"https://{social_link}"
        except Exception as e:
            print(f"Error extracting social link: {e}")
        
        return {
            "Type": investor_type,
            "Job Title": job_title,
            "Social Link": social_link
        }
        
    except Exception as e:
        print(f"Error extracting profile data from {investor_url}: {e}")
        return {
            "Type": "-",
            "Job Title": "-",
            "Social Link": "-"
        }

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
                "--disable-dev-shm-usage",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-extensions-except",
                "--disable-plugins-discovery",
                "--disable-default-apps",
                "--disable-background-timer-throttling",
                "--disable-backgrounding-occluded-windows",
                "--disable-renderer-backgrounding",
                "--disable-features=TranslateUI",
                "--disable-ipc-flooding-protection",
                "--enable-features=NetworkService,NetworkServiceLogging",
                "--force-color-profile=srgb",
                "--metrics-recording-only",
                "--no-pings",
                "--password-store=basic",
                "--use-mock-keychain",
                "--disable-component-extensions-with-background-pages",
                "--disable-background-networking",
                "--disable-sync",
                "--disable-translate",
                "--hide-scrollbars",
                "--mute-audio",
                "--no-default-browser-check",
                "--safebrowsing-disable-auto-update",
                "--disable-client-side-phishing-detection",
                "--disable-component-update",
                "--disable-domain-reliability",
                "--disable-features=AudioServiceOutOfProcess",
                "--disable-hang-monitor",
                "--disable-prompt-on-repost",
                "--disable-web-security",
                "--disable-features=VizDisplayCompositor"
            ],
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
            # Additional options for better session persistence
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
            timezone_id="America/New_York",
            permissions=["geolocation", "notifications"],
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1"
            }
        )
        
        print("✅ Playwright initialized with Chromium!")
        
        # Get the first page (or create a new one)
        page = browser.pages[0] if browser.pages else browser.new_page()
        
        # Set timeouts
        page.set_default_timeout(60000)  # 60 seconds
        page.set_default_navigation_timeout(60000)
        
        # Set up session storage for better login persistence
        try:
            # Navigate to Signal NFX to establish session
            page.goto("https://signal.nfx.com", wait_until="domcontentloaded")
            page.wait_for_timeout(1000)
            print("🌐 Session established with Signal NFX")
        except Exception as e:
            print(f"⚠️ Could not establish session: {e}")
        
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

def check_login_status(page):
    """Check if user is logged in to Signal NFX"""
    try:
        print("🔐 Checking login status...")
        page.goto("https://signal.nfx.com/login", wait_until="domcontentloaded")
        page.wait_for_timeout(2000)
        
        # Check if we're redirected to dashboard or if login form is present
        current_url = page.url
        print(f"📍 Current URL: {current_url}")
        
        # Look for login form elements
        login_form = page.query_selector("form")
        login_button = page.query_selector('button[type="submit"]')
        
        if "login" in current_url and (login_form or login_button):
            print("❌ Not logged in - login form detected")
            return False
        else:
            print("✅ Already logged in - no login form detected")
            return True
            
    except Exception as e:
        print(f"⚠️ Could not check login status: {e}")
        return False

def ensure_login(page):
    """Ensure user is logged in, prompt if not"""
    if not check_login_status(page):
        print("\n" + "="*60)
        print("🔐 LOGIN REQUIRED")
        print("="*60)
        print("Please log in to Signal NFX manually in the browser window.")
        print("The scraper will wait for you to complete the login process.")
        print("\nSteps:")
        print("1. Enter your email and password")
        print("2. Complete any 2FA if required")
        print("3. Wait for the dashboard to load")
        print("4. Press Enter here when login is complete")
        print("="*60)
        
        try:
            input("Press Enter when you have completed login...")
            print("✅ Login process completed!")
        except EOFError:
            print("⚠️ No input available, continuing with current session...")
        
        # Verify login again
        if check_login_status(page):
            print("✅ Login verified successfully!")
            return True
        else:
            print("⚠️ Login verification failed, but continuing...")
            return False
    else:
        print("✅ Already logged in!")
        return True





def scrape_signal_nfx(page, url):
    """Scrape investor data from Signal NFX using Playwright"""
    print(f"🚀 Loading Signal NFX Investors: {url}")
    
    # Navigate to the URL with Playwright
    try:
        print("📍 Navigating to Signal NFX Investors...")
        page.goto(url, wait_until="domcontentloaded")
        
        current_url = page.url
        page_title = page.title()
        
        print(f"✅ Page loaded successfully!")
        print(f"📍 Current URL: {current_url}")
        print(f"📄 Page Title: {page_title}")
        
        # Verify we're on Signal NFX
        if "signal.nfx.com" in current_url:
            print("✅ Confirmed: On Signal NFX website!")
        else:
            print(f"⚠️  Warning: Not on Signal NFX page. Current URL: {current_url}")
            
    except Exception as e:
        print(f"❌ Error loading Signal NFX: {e}")
        raise Exception(f"Failed to load Signal NFX: {e}")
    
    # Additional wait to ensure page is fully loaded
    print("⏳ Waiting for page to fully load...")
    page.wait_for_timeout(5000)  # Wait 5 seconds
    
    # Check page content
    try:
        page_content = page.content()
        if "tbody" in page_content.lower():
            print("✅ Page content looks correct - found investor table")
        else:
            print("⚠️  Page content might not be loading correctly")
            print("Page content length:", len(page_content))
    except Exception as e:
        print(f"Could not check page content: {e}")

    print("🔄 Extracting investor data...")
    if MAX_INVESTORS > 0:
        print(f"🎯 Target: Collecting up to {MAX_INVESTORS} investors")
    else:
        print("🎯 Target: Collecting all available investors")
    
    # Load existing investors to avoid duplicates
    existing_investors = load_existing_investors(OUTPUT_FILENAME)
    
    # Show initial CSV status
    initial_count = verify_csv_append(OUTPUT_FILENAME)
    
    # Extract data from all investor cards on the page
    print("📜 Extracting investor data from Signal NFX...")
    global collected_investor_data
    all_investor_data = []
    new_investors_count = 0
    skipped_investors_count = 0
    
    try:
        # Function to click load more button
        def click_load_more_button():
            """Click the load more button to load additional investors"""
            try:
                load_more_button = page.locator("button.btn-xs.sn-light-greyblue-accent-button.sn-center.mt3.mb2.btn.btn-default").first
                if load_more_button.is_visible():
                    print("🔄 Clicking 'Load More' button...")
                    load_more_button.click()
                    page.wait_for_timeout(3000)  # Wait for new content to load
                    return True
                else:
                    print("❌ Load more button not found or not visible")
                    return False
            except Exception as e:
                print(f"❌ Error clicking load more button: {e}")
                return False
        
        # Initial extraction
        soup = BeautifulSoup(page.content(), 'html.parser')
        investor_rows = soup.select("tbody tr")
        
        print(f"📊 Initial load: Found {len(investor_rows)} investor cards")
        
        # Try to load more investors by clicking the load more button
        load_attempt = 0
        
        while True:
            if click_load_more_button():
                load_attempt += 1
                print(f"🔄 Load attempt {load_attempt}")
                
                # Wait a bit more for content to load
                page.wait_for_timeout(2000)
                
                # Check if new investors were loaded
                new_soup = BeautifulSoup(page.content(), 'html.parser')
                new_investor_rows = new_soup.select("tbody tr")
                
                if len(new_investor_rows) > len(investor_rows):
                    print(f"✅ Loaded more investors! Now have {len(new_investor_rows)} total")
                    investor_rows = new_investor_rows
                else:
                    print("⚠️ No new investors loaded, stopping load more attempts")
                    break
            else:
                print("❌ Could not click load more button, stopping")
                break
        
        print(f"📊 Final count: Found {len(investor_rows)} investor cards after load more attempts")
        
        # Export backup CSV with main page data before profile extraction
        print("💾 Creating backup CSV with main page data...")
        backup_data = []
        
        for row in investor_rows:
            try:
                # Extract profile link from first td > div.flex > a.flex-column.pt1.mr3.items-center
                profile_link = "-"
                profile_element = row.select_one("td div.flex a.flex-column.pt1.mr3.items-center")
                if profile_element:
                    href = profile_element.get('href', '')
                    if href:
                        if href.startswith('/'):
                            profile_link = f"https://signal.nfx.com{href}"
                        elif href.startswith('http'):
                            profile_link = href
                        else:
                            profile_link = f"https://signal.nfx.com/{href}"
                
                # Extract investor name from div.pt1 > div.sn-investor-name-wrapper > a > strong.sn-investor-name
                investor_name = "-"
                name_element = row.select_one("div.pt1 div.sn-investor-name-wrapper a strong.sn-investor-name")
                if name_element:
                    investor_name = name_element.text.strip()
                
                # Extract company name from the a tag that comes before the investor type span
                company_name = "-"
                # Find the span.sn-small-link.hidden-xs (investor type) and get the a tag before it
                type_span = row.select_one("span.sn-small-link.hidden-xs")
                if type_span:
                    # Find the a tag that comes before this span
                    company_element = type_span.find_previous("a")
                    if company_element:
                        company_name = company_element.get_text(strip=True)
                
                # Extract investor type from span.sn-small-link.hidden-xs
                investor_type = "-"
                type_element = row.select_one("span.sn-small-link.hidden-xs")
                if type_element:
                    investor_type = type_element.text.strip()
                
                # Extract sweet spot (range) from td.text-center.pt2 > div.flex-column > div (both divs)
                sweet_spot = "-"
                sweet_spot_container = row.select_one("td.text-center.pt2 div.flex-column")
                if sweet_spot_container:
                    sweet_spot_divs = sweet_spot_container.select("div")
                    sweet_spot_texts = [div.get_text(strip=True) for div in sweet_spot_divs if div.get_text(strip=True)]
                    sweet_spot = " - ".join(sweet_spot_texts) if sweet_spot_texts else "-"
                
                # Extract investment location from td[style*="max-width: 400px"] > div[style*="position: relative"] > div.sn-clamp > div[style*="position: relative"] > span
                investment_location = "-"
                location_container = row.select_one("td[style*='max-width: 400px'] div[style*='position: relative'] div.sn-clamp div[style*='position: relative']")
                if location_container:
                    location_spans = location_container.select("span")
                    location_texts = [span.get_text(strip=True) for span in location_spans if span.get_text(strip=True)]
                    investment_location = ", ".join(location_texts) if location_texts else "-"
                
                # Extract top investment categories from the second div.sn-clamp > div[style*="position: relative"] > span
                top_categories = "-"
                # Look for the second div.sn-clamp in the row
                sn_clamp_divs = row.select("td[style*='max-width: 400px'] div[style*='position: relative'] div.sn-clamp")
                if len(sn_clamp_divs) > 1:
                    # Get the second sn-clamp div
                    second_sn_clamp = sn_clamp_divs[1]
                    # Look for div with position: relative inside this sn-clamp
                    relative_divs = second_sn_clamp.select("div[style*='position: relative']")
                    if relative_divs:
                        # Get spans from the relative div
                        category_spans = relative_divs[0].select("span")
                        category_texts = [span.get_text(strip=True) for span in category_spans if span.get_text(strip=True)]
                        top_categories = ", ".join(category_texts) if category_texts else "-"
                
                # Create investor data
                investor_data = {
                    "Investor Name": investor_name,
                    "Company Name": company_name,
                    "Investor Type": investor_type,
                    "Sweet Spot (Range)": sweet_spot,
                    "Investment Location": investment_location,
                    "Top Investment Categories": top_categories,
                    "Type": "-",  # Will be filled from profile page
                    "Job Title": "-",  # Will be filled from profile page
                    "Social Link": "-",  # Will be filled from profile page
                    "Profile Link": profile_link
                }
                
                # Add to backup data (all investors from main page)
                backup_data.append(investor_data)
                
                # Check if this investor is already collected (avoid duplicates in current session)
                if not any(data["Profile Link"] == profile_link for data in all_investor_data):
                    # Check if this investor already exists in CSV file
                    if profile_link in existing_investors:
                        skipped_investors_count += 1
                        print(f"⏭️ Skipping existing investor: {investor_name}")
                    else:
                        all_investor_data.append(investor_data)
                        new_investors_count += 1
                        print(f"✅ Found new investor: {investor_name}")
                
            except Exception as e:
                print(f"Error extracting investor data: {e}")
                continue
        
        print(f"📊 Found {new_investors_count} new investors, {skipped_investors_count} skipped total")
        
        # Save backup CSV with all main page data
        if backup_data:
            print(f"💾 Saving backup CSV with {len(backup_data)} investors from main page...")
            save_data(backup_data, "main_page_csv")
            print("✅ Backup CSV saved: main_page_csv.csv")
        
        # Check if there are any new investors to process
        if len(all_investor_data) == 0:
            print("✅ No new investors found! All investors are already in the CSV file.")
            return []
        
        # LEVEL 2: Extract profile data from each investor's profile page
        print("🎯 LEVEL 2: Extracting profile data from each investor's profile page...")
        print("💾 Data will be saved incrementally to CSV after each investor is processed")
        processed_count = 0
        
        for investor_data in all_investor_data:
            if MAX_INVESTORS > 0 and processed_count >= MAX_INVESTORS:
                break
                
            try:
                investor_url = investor_data["Profile Link"]
                print(f"🔍 Processing {processed_count + 1}/{len(all_investor_data)}: {investor_data['Investor Name']}")
                
                # Extract additional profile data
                profile_data = extract_investor_profile_data(page, investor_url)
                
                # Update the existing investor data with additional information
                investor_data["Type"] = profile_data["Type"]
                investor_data["Job Title"] = profile_data["Job Title"]
                investor_data["Social Link"] = profile_data["Social Link"]
                
                # Save incrementally to CSV
                save_incremental_data(investor_data, OUTPUT_FILENAME)
                
                collected_investor_data.append(investor_data)
                processed_count += 1
                
                print(f"✅ Processed {processed_count}/{len(all_investor_data)}: {investor_data['Investor Name']}")
                
                # Add delay between investors to avoid being blocked
                if processed_count < len(all_investor_data):
                    delay = random.uniform(1, 3)
                    print(f"⏳ Waiting {delay:.1f} seconds before next investor...")
                    page.wait_for_timeout(int(delay * 1000))
                
            except Exception as e:
                print(f"Error processing investor {investor_data.get('Investor Name', 'Unknown')}: {e}")
                continue
        
        print(f"🎉 Scraping completed! Processed {processed_count} investors")
        
        # Verify that data was appended correctly
        verify_csv_append(OUTPUT_FILENAME)
        
        return collected_investor_data
        
    except Exception as e:
        print(f"❌ Error processing Signal NFX page: {e}")
        return []

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

def load_existing_investors(filename):
    """Load existing investors from CSV file to avoid duplicates"""
    csv_path = f"{filename}.csv"
    existing_investors = set()
    
    if os.path.exists(csv_path):
        try:
            df = pd.read_csv(csv_path, encoding='utf-8-sig')
            if 'Profile Link' in df.columns:
                existing_investors = set(df['Profile Link'].dropna().tolist())
                print(f"📁 Found existing CSV with {len(existing_investors)} investors")
            else:
                print("⚠️ Existing CSV found but no 'Profile Link' column - will process all investors")
        except Exception as e:
            print(f"⚠️ Error reading existing CSV: {e} - will process all investors")
    else:
        print("📝 No existing CSV found - will create new file")
    
    return existing_investors

def save_incremental_data(investor_data, filename):
    """Save a single investor's data incrementally to CSV (append mode)"""
    csv_path = f"{filename}.csv"
    
    try:
        # Check if CSV file exists
        if os.path.exists(csv_path):
            # Read existing CSV to get the current row count
            existing_df = pd.read_csv(csv_path, encoding='utf-8-sig')
            current_count = len(existing_df)
            
            # Append new investor data to existing CSV
            df_new = pd.DataFrame([investor_data])
            df_new.to_csv(csv_path, mode='a', header=False, index=False, encoding='utf-8-sig')
            
            print(f"💾 Appended new investor #{current_count + 1}: {investor_data.get('Name', 'Unknown')}")
        else:
            # Create new CSV with header (first investor)
            df_new = pd.DataFrame([investor_data])
            df_new.to_csv(csv_path, index=False, encoding='utf-8-sig')
            print(f"💾 Created new CSV with first investor: {investor_data.get('Name', 'Unknown')}")
            
    except Exception as e:
        print(f"❌ Error saving investor data: {e}")
        # Fallback: try to save to a backup file
        backup_path = f"{filename}_backup.csv"
        try:
            df_new = pd.DataFrame([investor_data])
            df_new.to_csv(backup_path, mode='a', header=not os.path.exists(backup_path), index=False, encoding='utf-8-sig')
            print(f"💾 Saved to backup file: {backup_path}")
        except Exception as backup_e:
            print(f"❌ Backup save also failed: {backup_e}")

def save_partial_data():
    """Save any collected data when browser closes or script is interrupted"""
    global collected_investor_data
    if collected_investor_data:
        print("💾 Saving partial data before closing...")
        # Save to a separate partial file to avoid overwriting main CSV
        save_data(collected_investor_data, f"{OUTPUT_FILENAME}_partial")
        print(f"✅ Partial data saved: {len(collected_investor_data)} investors")
    else:
        print("📝 No data to save.")

def verify_csv_append(filename):
    """Verify that CSV file is being appended correctly"""
    csv_path = f"{filename}.csv"
    if os.path.exists(csv_path):
        try:
            df = pd.read_csv(csv_path, encoding='utf-8-sig')
            print(f"📊 CSV verification: {len(df)} total investors in {csv_path}")
            if 'Profile Link' in df.columns:
                unique_links = df['Profile Link'].nunique()
                print(f"📊 Unique profile links: {unique_links}")
                if len(df) != unique_links:
                    print("⚠️ Warning: Duplicate profile links detected!")
            return len(df)
        except Exception as e:
            print(f"❌ Error verifying CSV: {e}")
            return 0
    return 0

def process_existing_csv(page, csv_filename):
    """Process existing CSV file and extract profile data for each investor"""
    print(f"📁 Processing existing CSV file: {csv_filename}.csv")
    
    try:
        # Load existing CSV
        df = pd.read_csv(f"{csv_filename}.csv", encoding='utf-8-sig')
        print(f"📊 Found {len(df)} investors in CSV file")
        
        if 'Profile Link' not in df.columns:
            print("❌ Error: CSV file must contain 'Profile Link' column")
            return []
        
        # Check if profile data columns exist
        has_profile_data = all(col in df.columns for col in ['Type', 'Job Title', 'Social Link'])
        
        if has_profile_data:
            print("✅ CSV already contains profile data. Checking for missing data...")
            # Find rows with ALL THREE fields missing (empty or '-')
            missing_data = df[
                ((df['Type'].isna()) | (df['Type'] == '') | (df['Type'] == '-')) &
                ((df['Job Title'].isna()) | (df['Job Title'] == '') | (df['Job Title'] == '-')) &
                ((df['Social Link'].isna()) | (df['Social Link'] == '') | (df['Social Link'] == '-'))
            ]
            if len(missing_data) == 0:
                print("✅ All investors already have complete profile data!")
                return []
            else:
                print(f"📝 Found {len(missing_data)} investors with ALL profile fields missing")
                print("🔍 Will only process investors with missing Type, Job Title, AND Social Link data")
                investors_to_process = missing_data
        else:
            print("📝 CSV missing profile data columns. Adding them...")
            # Add missing columns
            df['Type'] = '-'
            df['Job Title'] = '-'
            df['Social Link'] = '-'
            investors_to_process = df
        
        # Process each investor
        processed_count = 0
        for index, row in investors_to_process.iterrows():
            try:
                investor_name = row.get('Investor Name', 'Unknown')
                profile_link = row.get('Profile Link', '')
                
                if not profile_link or profile_link == '-':
                    print(f"⏭️ Skipping {investor_name}: No profile link")
                    continue
                
                print(f"🔍 Processing {processed_count + 1}/{len(investors_to_process)}: {investor_name}")
                print(f"📝 All three profile fields are missing (Type, Job Title, Social Link)")
                
                # Extract profile data
                profile_data = extract_investor_profile_data(page, profile_link)
                
                # Update the row with new data
                df.at[index, 'Type'] = profile_data['Type']
                df.at[index, 'Job Title'] = profile_data['Job Title']
                df.at[index, 'Social Link'] = profile_data['Social Link']
                
                processed_count += 1
                print(f"✅ Processed {processed_count}/{len(investors_to_process)}: {investor_name}")
                
                # Save updated CSV after each investor
                df.to_csv(f"{csv_filename}.csv", index=False, encoding='utf-8-sig')
                
                # Add delay between investors (2-3 seconds)
                if processed_count < len(investors_to_process):
                    delay = random.uniform(2, 3)
                    print(f"⏳ Waiting {delay:.1f} seconds before next investor...")
                    page.wait_for_timeout(int(delay * 1000))
                
            except Exception as e:
                print(f"❌ Error processing {row.get('Investor Name', 'Unknown')}: {e}")
                continue
        
        print(f"🎉 CSV processing completed! Updated {processed_count} investors")
        return df.to_dict('records')
        
    except Exception as e:
        print(f"❌ Error processing CSV file: {e}")
        return []

def show_menu():
    """Display interactive menu for user selection"""
    print("\n" + "="*60)
    print("🚀 SIGNAL NFX INVESTORS SCRAPER")
    print("="*60)
    print("Choose your processing mode:")
    print()
    print("1️⃣  SCAN MAIN PAGE")
    print("   • Load Signal NFX main page")
    print("   • Extract all investor data from main page")
    print("   • Create backup CSV with main page data")
    print("   • Visit each profile page for additional data")
    print("   • Save complete data to CSV")
    print()
    print("2️⃣  PROCESS EXISTING CSV")
    print("   • Load existing CSV file")
    print("   • Visit each investor's profile page")
    print("   • Extract additional profile data")
    print("   • Update CSV with new information")
    print()
    print("="*60)
    
    while True:
        try:
            choice = input("Enter your choice (1 or 2): ").strip()
            if choice in ['1', '2']:
                return int(choice)
            else:
                print("❌ Invalid choice. Please enter 1 or 2.")
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            exit(0)
        except EOFError:
            # Fallback for non-interactive environments
            print("⚠️  No input available, defaulting to option 1 (SCAN MAIN PAGE)")
            return 1
        except Exception as e:
            print(f"❌ Error: {e}")
            # Fallback for other errors
            print("⚠️  Defaulting to option 1 (SCAN MAIN PAGE)")
            return 1

def signal_handler(signum, frame):
    """Handle Ctrl+C and other interruption signals"""
    print("\n🛑 Script interrupted! Saving collected data...")
    save_partial_data()
    sys.exit(0)

def main():
    """Main function to run the Signal NFX scraper"""
    choice = show_menu()
    
    print("\n" + "="*60)
    if choice == 1:
        print("🔍 MODE: SCAN MAIN PAGE")
        print(f"🎯 Target URL: {URL}")
        if MAX_INVESTORS > 0:
            print(f"📊 Investor Limit: {MAX_INVESTORS} investors")
        else:
            print("📊 Investor Limit: No limit (collect all)")
    else:
        print("📁 MODE: PROCESS EXISTING CSV")
        print("📊 Will process existing CSV file for profile data")
    print("="*60)
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
        
        if choice == 1:
            # Mode 1: Scan main page
            print("🎯 Navigating to Signal NFX...")
            print("🔄 Resume mode: Will check existing CSV and only process new investors")
            
            # Ensure user is logged in before scraping
            ensure_login(page)
            
            scraped_data = scrape_signal_nfx(page, URL)
            
            if scraped_data:
                print(f"🎉 Scraping completed! Processed {len(scraped_data)} new investors.")
                print(f"✅ All data has been saved incrementally to {OUTPUT_FILENAME}.csv")
                # Also save final JSON backup
                save_data(scraped_data, f"{OUTPUT_FILENAME}_final")
            else:
                print("✅ No new investors found - all data is already up to date!")
        else:
            # Mode 2: Process existing CSV
            csv_filename = input("Enter CSV filename (without .csv extension): ").strip()
            if not csv_filename:
                csv_filename = OUTPUT_FILENAME
            
            print(f"📁 Processing CSV file: {csv_filename}.csv")
            
            # Ensure user is logged in before processing CSV
            ensure_login(page)
            
            processed_data = process_existing_csv(page, csv_filename)
            
            if processed_data:
                print(f"🎉 CSV processing completed! Updated {len(processed_data)} investors.")
                print(f"✅ Updated data saved to {csv_filename}.csv")
            else:
                print("✅ No investors needed processing - all data is complete!")
    
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
