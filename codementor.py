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
URL = "https://www.codementor.io/search/mentors"
OUTPUT_FILENAME = "codementor_mentors"

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
                save_progress_and_exit()
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

def save_progress_and_exit():
    """Save current progress and exit when any key is pressed"""
    global scraped_data, current_browser, stop_scraping
    
    print("\n🛑 Key pressed! Saving progress and exiting...")
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

def get_browser_and_page(headless=False):
    """Initialize Playwright browser with Chromium"""
    print("🔒 Using Chromium browser with Playwright")
    print("📁 Profile Path: /Users/Nomercya/Library/Application Support/Google/Chrome/Profile 1")
    print(f"🖥️  Headless mode: {'ON' if headless else 'OFF'}")
    
    playwright = sync_playwright().start()
    
    try:
        print("🚀 Initializing Playwright with Chromium...")
        
        # Launch browser with Chromium (default Playwright browser)
        browser = playwright.chromium.launch_persistent_context(
            user_data_dir="/Users/Nomercya/Library/Application Support/Google/Chrome",
            headless=headless,  # Use parameter for headless mode
            args=[
                "--profile-directory=Profile 1",
                "--start-maximized",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--disable-web-security",
                "--disable-features=VizDisplayCompositor",
                "--disable-background-timer-throttling",
                "--disable-backgrounding-occluded-windows",
                "--disable-renderer-backgrounding"
            ],
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            # Add these to preserve session
            ignore_https_errors=True,
            accept_downloads=False
        )
        
        print("✅ Playwright initialized with Chromium!")
        
        # Get the first page (or create a new one)
        page = browser.pages[0] if browser.pages else browser.new_page()
        
        # Set timeouts
        page.set_default_timeout(60000)  # 60 seconds
        page.set_default_navigation_timeout(60000)
        
        return browser, page, playwright
        
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
    """Check if user is logged in to CodeMentor"""
    try:
        print("🔍 Checking login status...")
        
        # Navigate to the search page first
        page.goto(URL, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3000)  # Wait for page to load
        
        current_url = page.url
        page_title = page.title()
        
        print(f"📍 Current URL: {current_url}")
        print(f"📄 Page Title: {page_title}")
        
        # Check if we're on Arc.dev login page (CodeMentor's login service)
        if "arc.dev" in current_url and "login" in current_url:
            print("🔐 Redirected to Arc.dev login page - need to login with Google")
            return False
        
        # Check if we're on CodeMentor domain
        if "codementor.io" not in current_url:
            print("⚠️  Not on CodeMentor domain - may need to login")
            return False
        
        # Check for login indicators on CodeMentor
        login_elements = page.locator("//a[contains(text(), 'Login') or contains(text(), 'Sign in')]")
        login_count = login_elements.count()
        
        # Check for user profile indicators (logged in)
        profile_elements = page.locator("//a[contains(@href, '/profile') or contains(@href, '/dashboard')]")
        profile_count = profile_elements.count()
        
        # Check for logout button (indicates logged in)
        logout_elements = page.locator("//a[contains(text(), 'Logout') or contains(text(), 'Sign out')]")
        logout_count = logout_elements.count()
        
        # Check for mentor cards (indicates we're on the search page and logged in)
        mentor_cards = page.locator("div.jsx-d63913b6535ac8bc.mentor").count()
        
        print(f"🔍 Login elements found: {login_count}")
        print(f"🔍 Profile elements found: {profile_count}")
        print(f"🔍 Logout elements found: {logout_count}")
        print(f"🔍 Mentor cards found: {mentor_cards}")
        
        # If we find mentor cards, we're likely logged in and on the right page
        if mentor_cards > 0:
            print("✅ Found mentor cards - appears to be logged in to CodeMentor")
            return True
        
        # If we find login elements and no profile/logout elements, user is not logged in
        if login_count > 0 and profile_count == 0 and logout_count == 0:
            print("❌ User is NOT logged in to CodeMentor")
            return False
        else:
            print("✅ User appears to be logged in to CodeMentor")
            return True
            
    except Exception as e:
        print(f"⚠️  Error checking login status: {e}")
        # If we can't determine, assume not logged in for safety
        return False

def prompt_for_login():
    """Prompt user to login manually with delay"""
    print("\n" + "="*60)
    print("🔐 LOGIN REQUIRED")
    print("="*60)
    print("You need to log in to CodeMentor to access the mentor data.")
    print("The browser will open in visible mode so you can log in manually.")
    print("\n📋 INSTRUCTIONS:")
    print("1. You'll be redirected to Arc.dev (CodeMentor's login service)")
    print("2. Click 'Continue with Google' to login with your Google account")
    print("3. Complete the Google authentication process")
    print("4. You'll be redirected back to CodeMentor mentor search page")
    print("5. Wait for the countdown to finish or press ENTER when ready")
    print("6. The scraper will then switch to background mode")
    print("="*60)
    
    # Add a 30-second delay with countdown
    print("\n⏰ Waiting 30 seconds for you to login...")
    print("   (You can press ENTER anytime to continue early)")
    
    import threading
    import sys
    
    # Create a flag to track if user pressed enter
    user_ready = threading.Event()
    
    def wait_for_input():
        try:
            input()  # Wait for user input
            user_ready.set()
        except:
            pass
    
    # Start input thread
    input_thread = threading.Thread(target=wait_for_input, daemon=True)
    input_thread.start()
    
    # Countdown with visual feedback
    for i in range(30, 0, -1):
        if user_ready.is_set():
            print("\n✅ User ready! Proceeding immediately...")
            break
        
        # Print countdown every 5 seconds or in the last 10 seconds
        if i % 5 == 0 or i <= 10:
            print(f"   ⏳ {i} seconds remaining...")
        
        time.sleep(1)
    else:
        print("\n⏰ Time's up! Proceeding with scraping...")
    
    print("✅ Proceeding with scraping...")

def wait_for_codementor_redirect(page, max_wait_time=60):
    """Wait for redirect back to CodeMentor after login"""
    print("🔄 Waiting for redirect back to CodeMentor...")
    
    start_time = time.time()
    while time.time() - start_time < max_wait_time:
        current_url = page.url
        print(f"📍 Current URL: {current_url}")
        
        # Check if we're back on CodeMentor
        if "codementor.io" in current_url and "arc.dev" not in current_url:
            print("✅ Successfully redirected back to CodeMentor!")
            return True
        
        # Check if we're still on login page
        if "arc.dev" in current_url and "login" in current_url:
            print("⏳ Still on login page, waiting for redirect...")
        
        time.sleep(2)  # Check every 2 seconds
    
    print("⚠️  Timeout waiting for redirect to CodeMentor")
    return False

def minimize_browser_for_background(page):
    """Minimize browser window and prepare for background operation"""
    try:
        print("🔄 Preparing browser for background operation...")
        
        # Set a smaller viewport to reduce resource usage
        page.set_viewport_size({"width": 1024, "height": 768})
        print("✅ Viewport optimized for background operation")
        
        # Hide the browser window by moving it off-screen (macOS specific)
        try:
            page.evaluate("""
                window.moveTo(-2000, -2000);
                window.resizeTo(800, 600);
                window.blur();
            """)
            print("✅ Browser moved off-screen for background operation")
        except:
            print("ℹ️  Could not move browser off-screen")
        
        # Try to minimize the browser window
        try:
            page.evaluate("window.minimize()")
            print("✅ Browser window minimized")
        except:
            print("ℹ️  Could not minimize browser window")
        
        return True
        
    except Exception as e:
        print(f"⚠️  Error preparing browser for background: {e}")
        print("ℹ️  Continuing with visible browser...")
        return False

def keep_browser_hidden(page):
    """Keep browser window hidden/minimized"""
    try:
        # Move window off-screen and blur it
        page.evaluate("""
            window.moveTo(-2000, -2000);
            window.blur();
        """)
    except:
        pass

def save_session_state(page):
    """Save session cookies and localStorage to preserve login state"""
    try:
        print("💾 Saving session state...")
        
        # Get all cookies
        cookies = page.context.cookies()
        
        # Save cookies to file
        import json
        with open('session_cookies.json', 'w') as f:
            json.dump(cookies, f, indent=2)
        
        # Get localStorage data
        local_storage = page.evaluate("""
            () => {
                const data = {};
                for (let i = 0; i < localStorage.length; i++) {
                    const key = localStorage.key(i);
                    data[key] = localStorage.getItem(key);
                }
                return data;
            }
        """)
        
        # Save localStorage to file
        with open('session_localStorage.json', 'w') as f:
            json.dump(local_storage, f, indent=2)
        
        print("✅ Session state saved successfully!")
        
    except Exception as e:
        print(f"⚠️  Error saving session state: {e}")

def restore_session_state(page):
    """Restore session cookies and localStorage to maintain login state"""
    try:
        print("🔄 Restoring session state...")
        
        # Restore cookies
        import json
        import os
        
        if os.path.exists('session_cookies.json'):
            with open('session_cookies.json', 'r') as f:
                cookies = json.load(f)
            page.context.add_cookies(cookies)
            print("✅ Cookies restored")
        
        # Restore localStorage
        if os.path.exists('session_localStorage.json'):
            with open('session_localStorage.json', 'r') as f:
                local_storage = json.load(f)
            
            # Set localStorage items
            for key, value in local_storage.items():
                page.evaluate(f"localStorage.setItem('{key}', '{value}')")
            print("✅ localStorage restored")
        
        print("✅ Session state restored successfully!")
        
    except Exception as e:
        print(f"⚠️  Error restoring session state: {e}")

# REMOVED: restart_browser_in_headless_mode function
# We now keep the same browser session to preserve login state

def extract_social_links_from_profile(profile_url, browser):
    """Extract social links from a mentor's profile page (optimized for speed)"""
    try:
        print(f"🔗 Opening profile: {profile_url}")
        
        # Create a new page for the profile
        profile_page = browser.new_page()
        profile_page.set_default_timeout(15000)  # Reduced timeout
        
        # Navigate to the profile with faster settings
        profile_page.goto(profile_url, wait_until="domcontentloaded", timeout=15000)
        
        # Use faster loading strategy - just wait for content
        profile_page.wait_for_timeout(3000)  # Reduced wait time
        
        # Extract social links with faster method
        social_links = []
        try:
            # Look for social links container with shorter timeout
            social_container = profile_page.locator("div.social-links")
            if social_container.count() > 0:
                # Get all href links within the social-links div
                links = social_container.locator("a[href]").all()
                for link in links:
                    href = link.get_attribute("href")
                    if href:
                        social_links.append(href)
                print(f"✅ Found {len(social_links)} social links")
            else:
                print("⚠️  No social-links container found")
        except Exception as e:
            print(f"⚠️  Error extracting social links: {e}")
        
        # Close the profile page immediately
        profile_page.close()
        
        return ", ".join(social_links) if social_links else "N/A"
        
    except Exception as e:
        print(f"❌ Error opening profile {profile_url}: {e}")
        # Make sure to close page even on error
        try:
            profile_page.close()
        except:
            pass
        return "N/A"

def process_mentors_on_page(page, browser, existing_names=None, already_processed=None):
    """Process all mentors currently visible on the page and extract their social links (optimized)"""
    print("🔍 Processing mentors on current page (optimized for speed)...")
    
    # Get all mentor cards on the current page
    mentor_cards = page.locator("div.jsx-d63913b6535ac8bc.mentor").all()
    print(f"📊 Found {len(mentor_cards)} mentor cards on current page")
    
    processed_mentors = []
    if already_processed is None:
        already_processed = set()
    
    # First pass: collect all mentor data without opening profiles
    mentor_data_list = []
    for i, mentor_card in enumerate(mentor_cards, 1):
        try:
            # Extract basic info from the card
            name_element = mentor_card.locator("a h3.jsx-d63913b6535ac8bc").first
            if not name_element.is_visible():
                continue
                
            name = name_element.text_content().strip()
            
            # Skip if mentor already exists in CSV
            if existing_names and name in existing_names:
                print(f"⏭️  Skipping {name} (already in CSV)")
                continue
            
            # Skip if mentor already processed in this session
            if name in already_processed:
                print(f"⏭️  Skipping {name} (already processed this session)")
                continue
            
            # Get profile link
            profile_link_element = mentor_card.locator("a").first
            if not profile_link_element.is_visible():
                continue
                
            profile_link = profile_link_element.get_attribute("href")
            if not profile_link:
                continue
            
            # Make sure it's a full URL
            if profile_link.startswith("/"):
                profile_link = "https://www.codementor.io" + profile_link
            
            # Extract title
            title_element = mentor_card.locator("div.jsx-d63913b6535ac8bc.headline.section").first
            title = title_element.text_content().strip() if title_element.is_visible() else "N/A"
            
            # Extract price
            price_element = mentor_card.locator("div.jsx-d63913b6535ac8bc.rate").first
            price = price_element.text_content().strip() if price_element.is_visible() else "N/A"
            
            mentor_data_list.append({
                "name": name,
                "profile_link": profile_link,
                "title": title,
                "price": price
            })
            
        except Exception as e:
            print(f"❌ Error extracting mentor {i} data: {e}")
            continue
    
    print(f"👥 Found {len(mentor_data_list)} new mentors to process")
    
    # Second pass: process profiles quickly
    for i, mentor_data in enumerate(mentor_data_list, 1):
        try:
            print(f"👤 Processing mentor {i}/{len(mentor_data_list)}: {mentor_data['name']}")
            
            # Extract social links from profile (optimized)
            social_links = extract_social_links_from_profile(mentor_data['profile_link'], browser)
            
            final_mentor_data = {
                "Name": mentor_data['name'],
                "Profile Link": mentor_data['profile_link'],
                "Title": mentor_data['title'],
                "Price": mentor_data['price'],
                "Social Links": social_links
            }
            
            processed_mentors.append(final_mentor_data)
            already_processed.add(mentor_data['name'])  # Mark as processed
            print(f"✅ Completed {mentor_data['name']}")
            
            # Minimal delay between profile visits
            page.wait_for_timeout(300)  # Further reduced delay
            
        except Exception as e:
            print(f"❌ Error processing mentor {i}: {e}")
            continue
    
    print(f"🎉 Processed {len(processed_mentors)} NEW mentors from current page")
    return processed_mentors, already_processed

def find_and_click_load_more_button(page):
    """Find and click the Load More button using CodeMentor specific selector"""
    # Method 1: Try the exact CodeMentor CSS selector
    try:
        button = page.locator("button.ui__sc-1mmo7mk-0.kJekZt")
        if button.is_visible() and button.is_enabled():
            return button
    except:
        pass
    
    # Method 2: Try partial class matching for CodeMentor button
    try:
        button = page.locator("button[class*='ui__sc-1mmo7mk-0'][class*='kJekZt']")
        if button.is_visible() and button.is_enabled():
            return button
    except:
        pass
    
    # Method 3: Try finding button by text content
    try:
        button = page.locator("//button[contains(text(), 'Load more') or contains(text(), 'Show more') or contains(text(), 'More')]")
        if button.is_visible() and button.is_enabled():
            return button
    except:
        pass
    
    # Method 4: Try generic button selector as fallback
    try:
        button = page.locator("button")
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

def scrape_codementor(page, url, browser, existing_names=None):
    """Estekhraj-e etela'at az site-e CodeMentor using Playwright"""
    global scraped_data, stop_scraping
    
    print(f"🚀 Loading CodeMentor directly: {url}")
    
    if existing_names:
        print(f"🔄 Will skip {len(existing_names)} existing mentors")
    
    # Clear scraped data at start
    scraped_data = []
    stop_scraping = False
    
    # Navigate to the URL with Playwright
    try:
        print("📍 Navigating to CodeMentor...")
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        
        # Wait for page to load using alternative strategy (faster)
        print("⏳ Using alternative loading strategy for faster loading...")
        # Skip networkidle and go straight to element-based waiting
        page.wait_for_timeout(5000)  # Wait 5 seconds for initial load
        
        current_url = page.url
        page_title = page.title()
        
        print(f"✅ Page loaded successfully!")
        print(f"📍 Current URL: {current_url}")
        print(f"📄 Page Title: {page_title}")
        
        # Verify we're on CodeMentor
        if "codementor.io" in current_url:
            print("✅ Confirmed: On CodeMentor website!")
        else:
            print(f"⚠️  Warning: Not on CodeMentor page. Current URL: {current_url}")
            
    except Exception as e:
        print(f"❌ Error loading CodeMentor: {e}")
        raise Exception(f"Failed to load CodeMentor: {e}")
    
    # Additional wait to ensure page is fully loaded and mentor cards appear (optimized)
    print("⏳ Waiting for mentor cards to appear...")
    try:
        # Wait for at least one mentor card to appear with shorter timeout
        page.wait_for_selector("div.jsx-d63913b6535ac8bc.mentor", timeout=15000)
        print("✅ Mentor cards found on page!")
    except:
        print("⚠️  Mentor cards not found, but continuing...")
        page.wait_for_timeout(3000)  # Reduced fallback wait
    
    # Login check is now handled in main() function
    print("✅ Login status already verified in main function")
    
    # Check page content and debug
    try:
        page_content = page.content()
        print(f"📄 Page content length: {len(page_content)}")
        
        if "mentor" in page_content.lower() or "code" in page_content.lower():
            print("✅ Page content looks correct - found mentor/code keywords")
        else:
            print("⚠️  Page content might not be loading correctly")
            
        # Check if our specific selectors exist
        mentor_cards = page.locator("div.jsx-d63913b6535ac8bc.mentor").count()
        print(f"🔍 Found {mentor_cards} mentor cards with our selector")
        
        if mentor_cards == 0:
            print("⚠️  No mentor cards found with our selector. Checking for alternative selectors...")
            # Try to find any div with mentor class
            alt_mentors = page.locator("div[class*='mentor']").count()
            print(f"🔍 Found {alt_mentors} elements with 'mentor' in class name")
            
    except Exception as e:
        print(f"Could not check page content: {e}")

    print("🔍 First, processing mentors on the initial page...")
    # Process mentors on the initial page before clicking load more
    initial_mentors, already_processed = process_mentors_on_page(page, browser, existing_names)
    scraped_data.extend(initial_mentors)
    
    print("Shروع click kardan roye dokme-ye 'Load more mentors'...")
    if MAX_MENTORS > 0:
        print(f"🎯 Target: Collecting {MAX_MENTORS} NEW mentors (skipping existing ones)")
    else:
        print("🎯 Target: Collecting all available NEW mentors")
    
    click_count = 0
    max_clicks = 100  # Increased safety limit
    new_mentors_found = len(initial_mentors)
    
    while click_count < max_clicks and not stop_scraping:
        try:
            # Check if user wants to stop
            if stop_scraping:
                print("🛑 Stop signal received! Saving progress...")
                break
                
            # Check current mentors on page
            current_mentors = page.locator("div.jsx-d63913b6535ac8bc.mentor").all()
            print(f"📊 Total mentors on page: {len(current_mentors)}")
            
            # Count new mentors (not in existing CSV)
            if existing_names:
                new_mentors_count = 0
                for mentor_element in current_mentors:
                    try:
                        name_element = mentor_element.locator("a h3.jsx-d63913b6535ac8bc").first
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
            
            # Wait for new content to load (reduced time)
            print("Waiting for new mentors to load...")
            page.wait_for_timeout(3000)  # Reduced from 5000ms to 3000ms
            
            # Process the newly loaded mentors
            print(f"🔍 Processing new mentors after load more click {click_count}...")
            new_mentors, already_processed = process_mentors_on_page(page, browser, existing_names, already_processed)
            scraped_data.extend(new_mentors)
            new_mentors_found += len(new_mentors)
            
            print(f"📊 Total mentors processed so far: {new_mentors_found}")
            
            # Check if we've reached our target
            if MAX_MENTORS > 0 and new_mentors_found >= MAX_MENTORS:
                print(f"✅ Reached target of {MAX_MENTORS} mentors! Stopping...")
                break
            
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
        
        MENTOR_CARD_SELECTOR = "div.jsx-d63913b6535ac8bc.mentor"
        mentor_cards = soup.select(MENTOR_CARD_SELECTOR)
        
        print(f"Tedad-e nahayi {len(mentor_cards)} mentor peyda shod. Dar hale estekhraj...")
        
        # Filter out existing mentors and apply limit
        new_mentors = []
        for card in mentor_cards:
            name_element = card.select_one("a h3.jsx-d63913b6535ac8bc")
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
            # Extract name
            name_element = card.select_one("a h3.jsx-d63913b6535ac8bc")
            name = name_element.text.strip() if name_element else "N/A"
            
            # Extract profile link
            profile_link_element = card.select_one("a")
            profile_link = profile_link_element['href'] if profile_link_element and profile_link_element.has_attr('href') else "N/A"
            
            # Extract title
            title_element = card.select_one("div.jsx-d63913b6535ac8bc.headline.section")
            title = title_element.text.strip() if title_element else "N/A"
            
            # Extract price
            price_element = card.select_one("div.jsx-d63913b6535ac8bc.rate")
            price = price_element.text.strip() if price_element else "N/A"
            
            row = {
                "Name": name,
                "Profile Link": profile_link,
                "Title": title,
                "Price": price,
                "Social Links": "N/A"  # Will be filled by profile processing
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
    
    MENTOR_CARD_SELECTOR = "div.jsx-d63913b6535ac8bc.mentor"
    
    mentor_cards = soup.select(MENTOR_CARD_SELECTOR)
    
    data = []
    print(f"Tedad-e nahayi {len(mentor_cards)} mentor peyda shod. Dar hale estekhraj...")

    # Filter out existing mentors and apply limit
    new_mentors = []
    for card in mentor_cards:
        name_element = card.select_one("a h3.jsx-d63913b6535ac8bc")
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
        # Extract name
        name_element = card.select_one("a h3.jsx-d63913b6535ac8bc")
        name = name_element.text.strip() if name_element else "N/A"
        
        # Extract profile link
        profile_link_element = card.select_one("a")
        profile_link = profile_link_element['href'] if profile_link_element and profile_link_element.has_attr('href') else "N/A"
        
        # Extract title
        title_element = card.select_one("div.jsx-d63913b6535ac8bc.headline.section")
        title = title_element.text.strip() if title_element else "N/A"
        
        # Extract price
        price_element = card.select_one("div.jsx-d63913b6535ac8bc.rate")
        price = price_element.text.strip() if price_element else "N/A"
        
        row = {
            "Name": name,
            "Profile Link": profile_link,
            "Title": title,
            "Price": price
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
    
    print("--- CodeMentor Scraper (v22 - Login Check & Headless Mode) ---")
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
    playwright = None
    try:
        # Check if we have saved session
        import os
        has_saved_session = os.path.exists('session_cookies.json') and os.path.exists('session_localStorage.json')
        
        if has_saved_session:
            print("🚀 Starting Playwright with Chromium (HEADLESS mode - session found)...")
            browser, page, playwright = get_browser_and_page(headless=True)  # Start in headless mode
        else:
            print("🚀 Starting Playwright with Chromium (visible mode for login check)...")
            browser, page, playwright = get_browser_and_page(headless=False)  # Start in visible mode
        
        current_browser = browser  # Set global browser for interrupt handling
        
        # Debug: Show initial state
        print("🔍 Initial browser state:")
        print(f"   Current URL: {page.url}")
        print(f"   Page Title: {page.title()}")
        
        # Check user agent
        user_agent = page.evaluate("navigator.userAgent")
        print(f"   User Agent: {user_agent}")
        
        # Try to restore previous session
        restore_session_state(page)
        
        # Add initial delay to let user see the browser window
        print("\n⏰ Browser opened! Waiting 5 seconds for you to see the window...")
        time.sleep(5)
        
        # Check login status
        is_logged_in = check_login_status(page)
        
        if not is_logged_in:
            print("\n🔐 Login required detected!")
            prompt_for_login()
            
            # Wait for redirect back to CodeMentor after login
            redirect_success = wait_for_codementor_redirect(page)
            
            if not redirect_success:
                print("❌ Failed to redirect back to CodeMentor. Please try again.")
                return
            
            # Verify login after redirect
            print("🔍 Verifying login status after redirect...")
            is_logged_in = check_login_status(page)
            
            if not is_logged_in:
                print("❌ Still not logged in. Please try again or check your credentials.")
                return
            
            # Save session and switch to headless mode
            print("\n✅ Login successful! Saving session and switching to HEADLESS mode...")
            save_session_state(page)
            
            # Close current browser and start new one in headless mode
            print("🔄 Switching to HEADLESS mode for background operation...")
            browser.close()
            browser, page, playwright = get_browser_and_page(headless=True)
            current_browser = browser
            restore_session_state(page)
            
        else:
            print("✅ Already logged in! Proceeding with scraping...")
            # Save session cookies and state
            save_session_state(page)
        
        print("🎯 Starting scraping in HEADLESS background mode...")
        result_data = scrape_codementor(page, URL, browser, existing_names)
        
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
        
        if playwright:
            try:
                playwright.stop()
                print("✅ Playwright stopped.")
            except Exception as e:
                print(f"⚠️  Error stopping Playwright: {e}")

if __name__ == "__main__":
    main()
