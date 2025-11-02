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
URL = "https://www.openvc.app/investor-lists/series-a-investors"
OUTPUT_FILENAME = "openvc_seriesA_investors"

# <<<<<<< INVESTOR LIMIT CONFIGURATION >>>>>>>
# Set the maximum number of investors to collect (0 = no limit)
MAX_INVESTORS = 1746  # Change this to limit investors (e.g., 50, 100, 200)

# No credentials needed for OpenVC (public site)

# Global variable to store collected data
collected_investor_data = []

# <<<<<<< 1. CHROME PROFILE CONFIGURATION >>>>>>>
# Your Chrome profile path (automatically configured based on your system)
# Profile Path: /Users/Nomercya/Library/Application Support/Google/Chrome/Profile 1

# Login functions removed - OpenVC is a public site

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


# DealRoom-specific functions removed - using OpenVC structure

def scrape_openvc(page, url):
    """Scrape investor data from OpenVC seed investors using Playwright"""
    print(f"🚀 Loading OpenVC Seed Investors: {url}")
    
    # Navigate to the URL with Playwright
    try:
        print("📍 Navigating to OpenVC Seed Investors...")
        page.goto(url, wait_until="domcontentloaded")
        
        current_url = page.url
        page_title = page.title()
        
        print(f"✅ Page loaded successfully!")
        print(f"📍 Current URL: {current_url}")
        print(f"📄 Page Title: {page_title}")
        
        # Verify we're on OpenVC
        if "openvc.app" in current_url:
            print("✅ Confirmed: On OpenVC website!")
        else:
            print(f"⚠️  Warning: Not on OpenVC page. Current URL: {current_url}")
            
    except Exception as e:
        print(f"❌ Error loading OpenVC: {e}")
        raise Exception(f"Failed to load OpenVC: {e}")
    
    # Wait for page to fully load
    print("⏳ Waiting for page to fully load...")
    page.wait_for_timeout(8000)  # Wait 8 seconds
    
    # Check page content
    try:
        page_content = page.content()
        if "results_tb" in page_content.lower():
            print("✅ Page content looks correct - found investor table")
        else:
            print("⚠️  Page content might not be loading correctly")
            print("Page content length:", len(page_content))
    except Exception as e:
        print(f"Could not check page content: {e}")

    print("🔄 Starting to scrape investors...")
    if MAX_INVESTORS > 0:
        print(f"🎯 Target: Collecting up to {MAX_INVESTORS} investors")
    else:
        print("🎯 Target: Collecting all available investors")
    
    global collected_investor_data
    processed_count = 0
    page_number = 1
    
    while True:
        print(f"📄 Processing page {page_number}...")
        
        # Wait for table to load
        page.wait_for_timeout(5000)
        
        # Scroll to ensure all content is loaded
        print("📜 Scrolling to load all content...")
        page.keyboard.press("End")
        page.wait_for_timeout(3000)
        
        try:
            # Extract data from current page
            soup = BeautifulSoup(page.content(), 'html.parser')
            
            # Find the results table
            results_table = soup.select_one("table#results_tb")
            if not results_table:
                print("❌ Could not find results table")
                break
            
            # Find all investor rows in tbody
            investor_rows = results_table.select("tbody tr")
            print(f"📊 Found {len(investor_rows)} investor rows on page {page_number}")
            
            if len(investor_rows) == 0:
                print("❌ No investor rows found, stopping...")
                break
            
            # Process each investor row
            for row in investor_rows:
                if MAX_INVESTORS > 0 and processed_count >= MAX_INVESTORS:
                    print(f"✅ Reached target limit of {MAX_INVESTORS} investors!")
                    return collected_investor_data
                
                try:
                    # Extract name from td.nameCell
                    name = "-"
                    name_cell = row.select_one("td.nameCell")
                    if name_cell:
                        # Get text from a tag first (this is usually the clean name)
                        a_tag = name_cell.select_one("a")
                        if a_tag:
                            name = a_tag.get_text(strip=True)
                        else:
                            # Fallback to divs if no a tag
                            divs = name_cell.select("div")
                            name_parts = []
                            for div in divs:
                                div_text = div.get_text(strip=True)
                                if div_text and div_text not in name_parts:
                                    name_parts.append(div_text)
                            name = " ".join(name_parts) if name_parts else name_cell.get_text(strip=True)
                        
                        # Clean up the name - remove duplicate "VC firm" patterns
                        if name and "VC firm" in name:
                            # Split by "VC firm" and take the first part, then add "VC firm" once
                            parts = name.split("VC firm")
                            if len(parts) > 1:
                                clean_name = parts[0].strip()
                                if clean_name:
                                    name = f"{clean_name} VC firm"
                                else:
                                    name = "VC firm"
                    
                    # Extract location from td.text-nowrap (country links)
                    location = "-"
                    location_cell = row.select_one("td.text-nowrap")
                    if location_cell:
                        country_links = location_cell.select("a[href*='country/']")
                        countries = []
                        for link in country_links:
                            href = link.get('href', '')
                            if 'country/' in href:
                                country = href.split('country/')[-1]
                                countries.append(country)
                        location = ", ".join(countries) if countries else "-"
                    
                    # Extract check size from td[data-label="Check size"]
                    check_size = "-"
                    check_size_cell = row.select_one('td[data-label="Check size"]')
                    if check_size_cell:
                        check_size = check_size_cell.get_text(strip=True)
                    
                    # Extract stages - try multiple selectors to find the right cell
                    stages = "-"
                    # Try different selectors for stages cell
                    stages_cell = None
                    selectors = [
                        "td.d-none.d-lg-table-cell.text-nowrap",
                        "td[data-label*='stage']",
                        "td[data-label*='Stage']",
                        "td.text-nowrap"
                    ]
                    
                    for selector in selectors:
                        stages_cell = row.select_one(selector)
                        if stages_cell:
                            break
                    
                    if stages_cell:
                        # Try to get all text content from the cell first
                        cell_text = stages_cell.get_text(strip=True)
                        if cell_text and cell_text not in ["-", ""]:
                            # Clean up the stages text by adding proper spacing
                            stages = cell_text
                            # Add spaces before numbers and after periods
                            stages = stages.replace("1.", " 1.").replace("2.", " 2.").replace("3.", " 3.").replace("4.", " 4.").replace("5.", " 5.").replace("6.", " 6.")
                            # Add spaces before + signs
                            stages = stages.replace("+", " +")
                            # Clean up multiple spaces
                            stages = " ".join(stages.split())
                            # Add commas between different stage items
                            stages = stages.replace(" 1.", ", 1.").replace(" 2.", ", 2.").replace(" 3.", ", 3.").replace(" 4.", ", 4.").replace(" 5.", ", 5.").replace(" 6.", ", 6.")
                            # Remove leading comma if present
                            if stages.startswith(", "):
                                stages = stages[2:]
                        else:
                            # Fallback to extracting from links and spans
                            stage_links = stages_cell.select("a")
                            stage_texts = []
                            for link in stage_links:
                                span = link.select_one("span")
                                if span:
                                    stage_texts.append(span.get_text(strip=True))
                                else:
                                    stage_texts.append(link.get_text(strip=True))
                            if stage_texts:
                                stages = ", ".join(stage_texts)
                    
                    # Extract investment title from td.criteriaCell
                    investment_title = "-"
                    criteria_cell = row.select_one("td.criteriaCell")
                    if criteria_cell:
                        investment_title = criteria_cell.get_text(strip=True)
                    
                    # Extract open rate from td.cursor-pointer.text-nowrap
                    open_rate = "-"
                    open_rate_cell = row.select_one("td.cursor-pointer.text-nowrap")
                    if open_rate_cell:
                        span = open_rate_cell.select_one("span")
                        if span:
                            open_rate = span.get_text(strip=True)
                        else:
                            open_rate = open_rate_cell.get_text(strip=True)
                    
                    investor_data = {
                        "name": name,
                        "location": location,
                        "check_size": check_size,
                        "stages": stages,
                        "investment_title": investment_title,
                        "open_rate": open_rate
                    }
                    
                    # Check if all data is empty/invalid (all fields are "-")
                    all_empty = all(value == "-" for value in investor_data.values())
                    
                    if not all_empty:
                        # Save incrementally to CSV only if data is not all empty
                        save_incremental_data(investor_data, OUTPUT_FILENAME)
                        collected_investor_data.append(investor_data)
                        processed_count += 1
                        print(f"✅ Processed {processed_count}: {name}")
                    else:
                        print(f"⏭️ Skipped empty row: {name}")
                
                except Exception as e:
                    print(f"Error processing investor row: {e}")
                    continue
            
            # Try to go to next page
            print("🔄 Looking for next page button...")
            try:
                # Look for next page button: nav#pagination > ul.justify-content-center.pagination > li.page-item > a#pageNext
                next_button = page.locator("nav#pagination ul.justify-content-center.pagination li.page-item a#pageNext")
                
                if next_button.is_visible() and next_button.is_enabled():
                    print(f"➡️ Clicking next page button...")
                    next_button.click()
                    # Add longer delay between pages to be more human-like
                    delay = random.uniform(4, 7)
                    print(f"⏳ Waiting {delay:.1f} seconds before next page...")
                    page.wait_for_timeout(int(delay * 1000))
                    page_number += 1
                else:
                    print("❌ Next page button not found or disabled. Reached end of pages.")
                    break
                    
            except Exception as e:
                print(f"❌ Error clicking next page: {e}")
                break
            
        except Exception as e:
            print(f"❌ Error processing page {page_number}: {e}")
            break
    
    print(f"🎉 Scraping completed! Processed {processed_count} investors across {page_number} pages")
    return collected_investor_data

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

def save_incremental_data(investor_data, filename):
    """Save a single investor's data incrementally to CSV"""
    csv_path = f"{filename}.csv"
    
    # Check if CSV file exists
    if os.path.exists(csv_path):
        # Append to existing CSV
        df_new = pd.DataFrame([investor_data])
        df_new.to_csv(csv_path, mode='a', header=False, index=False, encoding='utf-8-sig')
    else:
        # Create new CSV with header
        df_new = pd.DataFrame([investor_data])
        df_new.to_csv(csv_path, index=False, encoding='utf-8-sig')
    
    print(f"💾 Incrementally saved: {investor_data.get('name', 'Unknown')}")

def clean_csv_file(filename):
    """Remove rows where all columns are '-' from existing CSV file"""
    csv_path = f"{filename}.csv"
    
    if os.path.exists(csv_path):
        try:
            # Read the CSV file
            df = pd.read_csv(csv_path)
            
            # Count rows before cleaning
            original_count = len(df)
            
            # Remove rows where all columns are '-'
            df_cleaned = df[~(df == '-').all(axis=1)]
            
            # Count rows after cleaning
            cleaned_count = len(df_cleaned)
            removed_count = original_count - cleaned_count
            
            if removed_count > 0:
                # Save the cleaned data back to CSV
                df_cleaned.to_csv(csv_path, index=False, encoding='utf-8-sig')
                print(f"🧹 Cleaned CSV: Removed {removed_count} empty rows (kept {cleaned_count} valid rows)")
            else:
                print(f"✅ CSV already clean: No empty rows found")
                
        except Exception as e:
            print(f"⚠️ Error cleaning CSV file: {e}")
    else:
        print(f"📝 No existing CSV file to clean: {csv_path}")

def save_partial_data():
    """Save any collected data when browser closes or script is interrupted"""
    global collected_investor_data
    if collected_investor_data:
        print("💾 Saving partial data before closing...")
        save_data(collected_investor_data, f"{OUTPUT_FILENAME}_partial")
        print(f"✅ Partial data saved: {len(collected_investor_data)} investors")
        # Clean the main CSV file
        clean_csv_file(OUTPUT_FILENAME)
    else:
        print("📝 No data to save.")

def signal_handler(signum, frame):
    """Handle Ctrl+C and other interruption signals"""
    print("\n🛑 Script interrupted! Saving collected data...")
    save_partial_data()
    sys.exit(0)

def main():
    """Main function to run the OpenVC seed investors scraper"""
    print("--- OpenVC Seed Investors Scraper ---")
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
        
        print("🎯 Navigating to OpenVC Seed Investors...")
        scraped_data = scrape_openvc(page, URL)
        
        if scraped_data:
            print(f"🎉 Scraping completed! Found {len(scraped_data)} investors.")
            print(f"✅ All data has been saved incrementally to {OUTPUT_FILENAME}.csv")
            # Also save final JSON backup
            save_data(scraped_data, f"{OUTPUT_FILENAME}_final")
            # Clean the CSV file to remove any empty rows
            print("🧹 Cleaning CSV file...")
            clean_csv_file(OUTPUT_FILENAME)
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
