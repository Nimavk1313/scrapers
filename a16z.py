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
URL = "https://a16z.com/portfolio/"
OUTPUT_FILENAME = "a16z_portfolio"

# <<<<<<< COMPANY LIMIT CONFIGURATION >>>>>>>
# Set the maximum number of companies to collect (0 = no limit)
MAX_COMPANIES = 0  # Change this to limit companies (e.g., 50, 100, 200)

# Global variable to store collected data
collected_investor_data = []

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




def extract_company_modal_data(page, company_card):
    """Extract detailed information from a16z company modal popup"""
    try:
        print(f"🔍 Clicking on company card to open modal...")
        
        # Click on the company card to open modal
        company_card.click()
        page.wait_for_timeout(2000)  # Wait for modal to open
        
        # Wait for modal to be visible
        try:
            page.wait_for_selector("div.portfolio-modal.show", timeout=10000)
            print("✅ Modal opened successfully")
        except:
            print("⚠️ Modal might not have opened, continuing...")
        
        soup = BeautifulSoup(page.content(), 'html.parser')
        
        # Extract website from div.portfolio-modal-box div.inner div.portfolio-modal-body div.modal-aside div.logo a
        website = "-"
        company_name = "-"
        try:
            logo_container = soup.select_one("div.portfolio-modal.show div.portfolio-modal-box div.inner div.portfolio-modal-body div.modal-aside div.logo")
            if logo_container:
                logo_link = logo_container.select_one("a")
                if logo_link:
                    website = logo_link.get('href', '').strip()
                    if website:
                        # Extract company name from website URL
                        if website.startswith('http://'):
                            website = website[7:]
                        elif website.startswith('https://'):
                            website = website[8:]
                        if website.startswith('www.'):
                            website = website[4:]
                        # Extract domain name (everything before first slash or dot)
                        domain_parts = website.split('/')[0].split('.')
                        if domain_parts:
                            company_name = domain_parts[0].title()
                        print(f"✅ Found website: {website}, company name: {company_name}")
        except Exception as e:
            print(f"Error extracting website: {e}")
        
        # Extract milestones from div.portfolio-modal-box div.inner div.portfolio-modal-body div.modal-aside div.company-info div.info-list ul.list li
        milestones = "-"
        try:
            info_list = soup.select_one("div.portfolio-modal.show div.portfolio-modal-box div.inner div.portfolio-modal-body div.modal-aside div.company-info div.info-list ul.list")
            if info_list:
                milestone_items = info_list.select("li")
                milestone_texts = [li.text.strip() for li in milestone_items if li.text.strip()]
                milestones = " | ".join(milestone_texts) if milestone_texts else "-"
                print(f"✅ Found milestones: {milestones}")
        except Exception as e:
            print(f"Error extracting milestones: {e}")
        
        # Extract social links from div.portfolio-modal-box div.inner div.portfolio-modal-body div.right ul.social-links li a
        social_links = "-"
        try:
            social_container = soup.select_one("div.portfolio-modal.show div.portfolio-modal-box div.inner div.portfolio-modal-body div.right ul.social-links")
            if social_container:
                social_items = social_container.select("li a")
                social_hrefs = [a.get('href', '').strip() for a in social_items if a.get('href', '').strip()]
                social_links = " | ".join(social_hrefs) if social_hrefs else "-"
                print(f"✅ Found social links: {social_links}")
        except Exception as e:
            print(f"Error extracting social links: {e}")
        
        # Extract about text from div.modal-content div.modal-content-inner div[data-v-49a33c22] div.block (h3 "company profile" + div[data-v-49a33c22])
        about = "-"
        try:
            modal_content = soup.select_one("div.portfolio-modal.show div.portfolio-modal-box div.inner div.portfolio-modal-body div.modal-content div.modal-content-inner")
            if modal_content:
                # Find div with data-v-49a33c22 attribute
                content_divs = modal_content.select("div[data-v-49a33c22]")
                for div in content_divs:
                    # Look for div.block inside
                    block_div = div.select_one("div.block")
                    if block_div:
                        # Check if this block contains h3 with "company profile" text
                        h3_tag = block_div.select_one("h3")
                        if h3_tag and "company profile" in h3_tag.text.lower():
                            # Get the text from the div[data-v-49a33c22] after h3
                            about_div = block_div.select_one("div[data-v-49a33c22]")
                            if about_div:
                                about = about_div.text.strip()
                                print(f"✅ Found about text: {about[:100]}...")
                                break
        except Exception as e:
            print(f"Error extracting about text: {e}")
        
        # Extract builders from div.right div.builders p
        builders = "-"
        try:
            right_container = soup.select_one("div.portfolio-modal.show div.portfolio-modal-box div.inner div.portfolio-modal-body div.right")
            if right_container:
                builders_div = right_container.select_one("div.builders")
                if builders_div:
                    builders_p = builders_div.select_one("p")
                    if builders_p:
                        builders = builders_p.text.strip()
                        print(f"✅ Found builders: {builders}")
        except Exception as e:
            print(f"Error extracting builders: {e}")
        
        # Close modal by clicking outside or pressing escape
        try:
            page.keyboard.press("Escape")
            page.wait_for_timeout(1000)
        except:
            pass
        
        return {
            "Name": company_name,
            "Website": website,
            "Milestones": milestones,
            "Social Links": social_links,
            "About": about,
            "Builders": builders
        }
        
    except Exception as e:
        print(f"Error extracting modal data: {e}")
        return {
            "Name": "-",
            "Website": "-",
            "Milestones": "-",
            "Social Links": "-",
            "About": "-",
            "Builders": "-"
        }

def scrape_a16z_portfolio(page, url):
    """Scrape company data from a16z portfolio using Playwright"""
    print(f"🚀 Loading a16z Portfolio: {url}")
    
    # Navigate to the URL with Playwright
    try:
        print("📍 Navigating to a16z Portfolio...")
        page.goto(url, wait_until="domcontentloaded")
        
        current_url = page.url
        page_title = page.title()
        
        print(f"✅ Page loaded successfully!")
        print(f"📍 Current URL: {current_url}")
        print(f"📄 Page Title: {page_title}")
        
        # Verify we're on a16z portfolio
        if "a16z.com" in current_url and "portfolio" in current_url:
            print("✅ Confirmed: On a16z portfolio page!")
        else:
            print(f"⚠️  Warning: Not on a16z portfolio page. Current URL: {current_url}")
            
    except Exception as e:
        print(f"❌ Error loading a16z portfolio: {e}")
        raise Exception(f"Failed to load a16z portfolio: {e}")
    
    # Additional wait to ensure page is fully loaded
    print("⏳ Waiting for page to fully load...")
    page.wait_for_timeout(5000)  # Wait 5 seconds
    
    # Check page content
    try:
        page_content = page.content()
        if "company-grid-item" in page_content.lower():
            print("✅ Page content looks correct - found company cards")
        else:
            print("⚠️  Page content might not be loading correctly")
            print("Page content length:", len(page_content))
    except Exception as e:
        print(f"Could not check page content: {e}")

    print("🔄 Processing company cards...")
    if MAX_COMPANIES > 0:
        print(f"🎯 Target: Collecting up to {MAX_COMPANIES} companies")
    else:
        print("🎯 Target: Collecting all available companies")
    
    # Load existing companies to avoid duplicates
    existing_companies = load_existing_companies(OUTPUT_FILENAME)
    
    # Show initial CSV status
    initial_count = verify_csv_append(OUTPUT_FILENAME)
    
    # Extract company cards from the page
    print("📜 Collecting company data from portfolio page...")
    global collected_investor_data
    all_company_data = []
    new_companies_count = 0
    skipped_companies_count = 0
    
    try:
        # Get all company cards on the page
        soup = BeautifulSoup(page.content(), 'html.parser')
        company_cards = soup.select("div.column.grid-item.company-grid-item")
        
        print(f"📊 Found {len(company_cards)} company cards on the page")
        
        # Process each company card
        for i, card in enumerate(company_cards):
            try:
                print(f"🔍 Processing company card {i + 1}/{len(company_cards)}")
                
                # Create a locator for this specific card to click on it
                card_locator = page.locator(f"div.column.grid-item.company-grid-item").nth(i)
                
                # Extract data from modal popup
                company_data = extract_company_modal_data(page, card_locator)
                
                # Check if this company is already collected (avoid duplicates in current session)
                if not any(data["Website"] == company_data["Website"] for data in all_company_data):
                    # Check if this company already exists in CSV file
                    if company_data["Website"] in existing_companies:
                        skipped_companies_count += 1
                        print(f"⏭️ Skipping existing company: {company_data['Name']}")
                    else:
                        all_company_data.append(company_data)
                        new_companies_count += 1
                        
                        # Save incrementally to CSV
                        save_incremental_data(company_data, OUTPUT_FILENAME)
                        
                        print(f"✅ Processed {new_companies_count}: {company_data['Name']}")
                        
                        # Add delay between companies to avoid overwhelming the site
                        if i < len(company_cards) - 1:
                            delay = random.uniform(1, 3)
                            print(f"⏳ Waiting {delay:.1f} seconds before next company...")
                            page.wait_for_timeout(int(delay * 1000))
                
                # Check if we've reached the limit for new companies
                if MAX_COMPANIES > 0 and new_companies_count >= MAX_COMPANIES:
                    print(f"✅ Reached target limit of {MAX_COMPANIES} new companies!")
                    break
                
            except Exception as e:
                print(f"Error processing company card {i + 1}: {e}")
                continue
        
        print(f"🎉 Scraping completed!")
        print(f"📊 New companies found: {new_companies_count}")
        print(f"⏭️ Skipped existing companies: {skipped_companies_count}")
        print(f"🎯 Total new companies processed: {len(all_company_data)}")
        
        # Verify that data was appended correctly
        verify_csv_append(OUTPUT_FILENAME)
        
        return all_company_data
        
    except Exception as e:
        print(f"❌ Error processing company cards: {e}")
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

def load_existing_companies(filename):
    """Load existing companies from CSV file to avoid duplicates"""
    csv_path = f"{filename}.csv"
    existing_companies = set()
    
    if os.path.exists(csv_path):
        try:
            df = pd.read_csv(csv_path, encoding='utf-8-sig')
            if 'Website' in df.columns:
                existing_companies = set(df['Website'].dropna().tolist())
                print(f"📁 Found existing CSV with {len(existing_companies)} companies")
            else:
                print("⚠️ Existing CSV found but no 'Website' column - will process all companies")
        except Exception as e:
            print(f"⚠️ Error reading existing CSV: {e} - will process all companies")
    else:
        print("📝 No existing CSV found - will create new file")
    
    return existing_companies

def save_incremental_data(company_data, filename):
    """Save a single company's data incrementally to CSV (append mode)"""
    csv_path = f"{filename}.csv"
    
    try:
        # Check if CSV file exists
        if os.path.exists(csv_path):
            # Read existing CSV to get the current row count
            existing_df = pd.read_csv(csv_path, encoding='utf-8-sig')
            current_count = len(existing_df)
            
            # Append new company data to existing CSV
            df_new = pd.DataFrame([company_data])
            df_new.to_csv(csv_path, mode='a', header=False, index=False, encoding='utf-8-sig')
            
            print(f"💾 Appended new company #{current_count + 1}: {company_data.get('Name', 'Unknown')}")
        else:
            # Create new CSV with header (first company)
            df_new = pd.DataFrame([company_data])
            df_new.to_csv(csv_path, index=False, encoding='utf-8-sig')
            print(f"💾 Created new CSV with first company: {company_data.get('Name', 'Unknown')}")
            
    except Exception as e:
        print(f"❌ Error saving company data: {e}")
        # Fallback: try to save to a backup file
        backup_path = f"{filename}_backup.csv"
        try:
            df_new = pd.DataFrame([company_data])
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
        print(f"✅ Partial data saved: {len(collected_investor_data)} companies")
    else:
        print("📝 No data to save.")

def verify_csv_append(filename):
    """Verify that CSV file is being appended correctly"""
    csv_path = f"{filename}.csv"
    if os.path.exists(csv_path):
        try:
            df = pd.read_csv(csv_path, encoding='utf-8-sig')
            print(f"📊 CSV verification: {len(df)} total companies in {csv_path}")
            if 'Website' in df.columns:
                unique_websites = df['Website'].nunique()
                print(f"📊 Unique websites: {unique_websites}")
                if len(df) != unique_websites:
                    print("⚠️ Warning: Duplicate websites detected!")
            return len(df)
        except Exception as e:
            print(f"❌ Error verifying CSV: {e}")
            return 0
    return 0

def signal_handler(signum, frame):
    """Handle Ctrl+C and other interruption signals"""
    print("\n🛑 Script interrupted! Saving collected data...")
    save_partial_data()
    sys.exit(0)

def main():
    """Main function to run the a16z Portfolio scraper"""
    print("--- a16z Portfolio Scraper ---")
    print("🔒 Using Chromium browser with Playwright")
    print(f"🎯 Target URL: {URL}")
    if MAX_COMPANIES > 0:
        print(f"📊 Company Limit: {MAX_COMPANIES} companies")
    else:
        print("📊 Company Limit: No limit (collect all)")
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
        
        print("🎯 Navigating to a16z Portfolio...")
        print("🔄 Resume mode: Will check existing CSV and only process new companies")
        scraped_data = scrape_a16z_portfolio(page, URL)
        
        if scraped_data:
            print(f"🎉 Scraping completed! Processed {len(scraped_data)} new companies.")
            print(f"✅ All data has been saved incrementally to {OUTPUT_FILENAME}.csv")
            # Also save final JSON backup
            save_data(scraped_data, f"{OUTPUT_FILENAME}_final")
        else:
            print("✅ No new companies found - all data is already up to date!")
    
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
