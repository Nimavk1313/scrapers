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
URL = "https://mentorship.lfx.linuxfoundation.org/#mentors"
OUTPUT_FILENAME = "linuxfoundation_mentors"

# <<<<<<< MENTOR LIMIT CONFIGURATION >>>>>>>
# Set the maximum number of mentors to collect (0 = no limit)
MAX_MENTORS = 200  # Change this to limit mentors (e.g., 50, 100, 200)

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

def get_browser_and_page(headless=True):
    """Initialize Playwright browser with Chromium"""
    print("🔒 Using Chromium browser with Playwright")
    print("📁 Profile Path: /Users/Nomercya/Library/Application Support/Google/Chrome/Profile 1")
    print(f"🖥️  Headless mode: {'ON' if headless else 'OFF'}")
    
    playwright = sync_playwright().start()
    
    try:
        print("🚀 Initializing Playwright with Chromium...")
        
        # Launch browser with Chromium (default Playwright browser)
        browser = playwright.chromium.launch_persistent_context(
            user_data_dir="/tmp/scraper_chrome_profile",
            headless=headless,  # Use parameter for headless mode
            args=[
                "--profile-directory=ScraperProfile",
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
    """Check if user is logged in to Linux Foundation Mentorship"""
    try:
        print("🔍 Checking login status...")
        
        # Navigate to the search page first
        page.goto(URL, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3000)  # Wait for page to load
        
        current_url = page.url
        page_title = page.title()
        
        print(f"📍 Current URL: {current_url}")
        print(f"📄 Page Title: {page_title}")
        
        # Check if we're on Linux Foundation domain
        if "mentorship.lfx.linuxfoundation.org" not in current_url:
            print("⚠️  Not on Linux Foundation Mentorship domain")
            return False
        
        # Check for login indicators
        login_elements = page.locator("//a[contains(text(), 'Login') or contains(text(), 'Sign in')]")
        login_count = login_elements.count()
        
        # Check for user profile indicators (logged in)
        profile_elements = page.locator("//a[contains(@href, '/profile') or contains(@href, '/dashboard')]")
        profile_count = profile_elements.count()
        
        # Check for logout button (indicates logged in)
        logout_elements = page.locator("//a[contains(text(), 'Logout') or contains(text(), 'Sign out')]")
        logout_count = logout_elements.count()
        
        # Check for mentor cards (indicates we're on the right page)
        mentor_cards = page.locator("div.card-align").count()
        
        print(f"🔍 Login elements found: {login_count}")
        print(f"🔍 Profile elements found: {profile_count}")
        print(f"🔍 Logout elements found: {logout_count}")
        print(f"🔍 Mentor cards found: {mentor_cards}")
        
        # If we find mentor cards, we're on the right page
        if mentor_cards > 0:
            print("✅ Found mentor cards - appears to be on the correct page")
            return True
        
        # For Linux Foundation, we might not need login for basic access
        print("✅ Linux Foundation Mentorship page loaded successfully")
        return True
            
    except Exception as e:
        print(f"⚠️  Error checking login status: {e}")
        # If we can't determine, assume we can proceed
        return True

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

def separate_projects_and_mentees(project_data):
    """Separate project names from mentee names in the project data"""
    if not project_data or project_data == "N/A":
        return {"projects": "N/A", "mentees": "N/A"}
    
    items = [item.strip() for item in project_data.split(",")]
    projects = []
    mentees = []
    
    for item in items:
        # Check if it's a project (contains organization names or long descriptions)
        if any(keyword in item for keyword in ["CNCF", "Open Mainframe Project", "Hyperledger", "FINOS", "Term", "Mentorship", ":", "project", "Project"]):
            projects.append(item)
        # Check if it's a mentee name (short, usually 1-3 words, no special characters)
        elif len(item.split()) <= 3 and not any(char in item for char in [":", "-", "(", ")", "Term", "project", "Project"]):
            mentees.append(item)
        else:
            # If uncertain, treat as project
            projects.append(item)
    
    return {
        "projects": ", ".join(projects) if projects else "N/A",
        "mentees": ", ".join(mentees) if mentees else "N/A"
    }

def cleanup_extra_tabs(context, main_page):
    """Clean up any extra tabs that might have been left open"""
    try:
        pages = context.pages
        if len(pages) > 1:
            for page in pages:
                if page != main_page and not page.is_closed():
                    page.close()
                    print("🗑️  Cleaned up extra tab")
    except Exception as e:
        print(f"⚠️  Error cleaning up tabs: {e}")

def extract_detailed_profile_info_from_tab(profile_page, mentor_name):
    """Extract detailed information from mentor profile page in new tab"""
    try:
        print(f"🔗 Extracting detailed info for: {mentor_name}")
        
        # Wait for page to load
        profile_page.wait_for_timeout(1000)
        
        # Get the current URL as the profile link
        current_url = profile_page.url
        print(f"📍 Profile URL: {current_url}")
        
        # Extract social links from div.project-repo.w-100
        social_links = []
        try:
            project_repo_elements = profile_page.locator("div.project-repo.w-100 a").all()
            for element in project_repo_elements:
                href = element.get_attribute("href")
                if href:
                    social_links.append(href)
            print(f"✅ Found {len(social_links)} social links")
        except Exception as e:
            print(f"⚠️  Error extracting social links: {e}")
        
        # Extract skills from ul.tag-list.skill-list
        detailed_skills = []
        try:
            skill_list_elements = profile_page.locator("ul.tag-list.skill-list li").all()
            for element in skill_list_elements:
                skill_text = element.text_content().strip()
                if skill_text:
                    detailed_skills.append(skill_text)
            print(f"✅ Found {len(detailed_skills)} detailed skills")
        except Exception as e:
            print(f"⚠️  Error extracting detailed skills: {e}")
        
        return {
            "profile_url": current_url,
            "social_links": ", ".join(social_links) if social_links else "N/A",
            "user_features": ", ".join(detailed_skills) if detailed_skills else "N/A"
        }
        
    except Exception as e:
        print(f"❌ Error extracting detailed profile info: {e}")
        return {"profile_url": "N/A", "social_links": "N/A", "user_features": "N/A"}

def refresh_mentor_cards_list(page):
    """Refresh the mentor cards list after aggressive scrolling"""
    try:
        print("🔄 Refreshing mentor cards list after aggressive scroll...")
        # Get fresh mentor cards list
        mentor_cards = page.locator("div.card-align").all()
        print(f"📊 Refreshed: Found {len(mentor_cards)} total mentor cards")
        return mentor_cards
    except Exception as e:
        print(f"⚠️  Error refreshing mentor cards: {e}")
        return []

def process_mentors_on_page(page, browser, existing_names=None, already_processed=None):
    """Process only NEW mentors currently visible on the page by clicking their profile buttons"""
    print("🔍 Processing NEW mentors on current page by clicking profile buttons...")
    
    # Get all mentor cards on the current page
    mentor_cards = page.locator("div.card-align").all()
    print(f"📊 Found {len(mentor_cards)} total mentor cards on current page")
    
    processed_mentors = []
    if already_processed is None:
        already_processed = set()
    
    # First, identify which mentors are new (not already processed)
    new_mentor_cards = []
    for mentor_card in mentor_cards:
        try:
            name_element = mentor_card.locator("a.card-title span").first
            if name_element.is_visible():
                name = name_element.text_content().strip()
                
                # Skip if mentor already exists in CSV
                if existing_names and name in existing_names:
                    continue
                
                # Skip if mentor already processed in this session
                if name in already_processed:
                    continue
                
                new_mentor_cards.append((mentor_card, name))
        except Exception as e:
            print(f"⚠️  Error checking mentor card: {e}")
            continue
    
    print(f"📊 Found {len(new_mentor_cards)} NEW mentors to process")
    
    # Process only the new mentor cards
    for i, (mentor_card, name) in enumerate(new_mentor_cards, 1):
        try:
            print(f"👤 Processing mentor {i}/{len(new_mentor_cards)}: {name}")
            
            # Check if the mentor card is still visible (important after scrolling)
            if not mentor_card.is_visible():
                print(f"⚠️  Mentor card for {name} is not visible, using aggressive scroll...")
                try:
                    # Use aggressive scroll to load more content
                    aggressive_scroll_success = aggressive_scroll_to_load_mentors(page)
                    
                    if aggressive_scroll_success:
                        # Refresh the mentor card reference after aggressive scroll
                        try:
                            # Get fresh mentor cards and find the one we need
                            fresh_mentor_cards = page.locator("div.card-align").all()
                            mentor_found = False
                            
                            for fresh_card in fresh_mentor_cards:
                                try:
                                    fresh_name_element = fresh_card.locator("a.card-title span").first
                                    if fresh_name_element.is_visible():
                                        fresh_name = fresh_name_element.text_content().strip()
                                        if fresh_name == name:
                                            mentor_card = fresh_card  # Update reference
                                            mentor_found = True
                                            break
                                except:
                                    continue
                            
                            if not mentor_found:
                                print(f"⚠️  Could not find mentor card for {name} after aggressive scroll, skipping...")
                                continue
                        except Exception as refresh_error:
                            print(f"⚠️  Error refreshing mentor card for {name}: {refresh_error}")
                            continue
                    else:
                        print(f"⚠️  Aggressive scroll failed, skipping {name}...")
                        continue
                except Exception as e:
                    print(f"⚠️  Error handling mentor card visibility for {name}: {e}")
                    continue
            
            # Extract project information from the card
            projects = []
            try:
                project_elements = mentor_card.locator("div.icons-container img[title]").all()
                for project_element in project_elements:
                    project_title = project_element.get_attribute("title")
                    if project_title:
                        projects.append(project_title)
            except Exception as e:
                print(f"⚠️  Error extracting projects: {e}")
            
            # Click on the "View Profile" button (improved error handling)
            try:
                # Try to find the profile button with multiple selectors
                profile_button = None
                button_selectors = [
                    "div.footer-btn.center-btn-text.mt-3",
                    "div.footer-btn",
                    "button[class*='footer']",
                    "a[class*='profile']"
                ]
                
                for selector in button_selectors:
                    try:
                        button = mentor_card.locator(selector).first
                        if button.is_visible():
                            profile_button = button
                            break
                    except:
                        continue
                
                if profile_button and profile_button.is_visible():
                    print(f"🖱️  Clicking profile button for {name}")
                    
                    # Scroll the button into view before clicking
                    profile_button.scroll_into_view_if_needed()
                    page.wait_for_timeout(500)
                    
                    # Click the button
                    profile_button.click()
                    page.wait_for_timeout(1000)  # Wait for navigation
                    
                    # Check if we're on a profile page
                    current_url = page.url
                    if "mentor/" in current_url:
                        # Extract detailed information from the profile page
                        detailed_info = extract_detailed_profile_info_from_tab(page, name)
                        
                        # Go back to the mentors page
                        page.go_back()
                        page.wait_for_timeout(1000)  # Wait for back navigation
                    else:
                        print(f"⚠️  Did not navigate to profile page for {name}")
                        detailed_info = {"profile_url": "N/A", "social_links": "N/A", "user_features": "N/A"}
                    
                else:
                    print(f"⚠️  Profile button not found or not visible for {name}")
                    detailed_info = {"profile_url": "N/A", "social_links": "N/A", "user_features": "N/A"}
                    
            except Exception as e:
                print(f"❌ Error clicking profile button for {name}: {e}")
                detailed_info = {"profile_url": "N/A", "social_links": "N/A", "user_features": "N/A"}
            
            # Separate projects and mentees
            project_data = ", ".join(projects) if projects else "N/A"
            separated_data = separate_projects_and_mentees(project_data)
            
            # Create final mentor data
            final_mentor_data = {
                "Name": name,
                "Profile Link": detailed_info["profile_url"],
                "Projects": separated_data["projects"],
                "Mentees": separated_data["mentees"],
                "Social Links": detailed_info["social_links"],
                "User Features": detailed_info["user_features"]
            }
            
            processed_mentors.append(final_mentor_data)
            already_processed.add(name)  # Mark as processed
            print(f"✅ Completed {name}")
            
            # Minimal delay between mentors (no need to scroll back anymore)
            page.wait_for_timeout(100)
            
        except Exception as e:
            print(f"❌ Error processing mentor {i}: {e}")
            continue
    
    print(f"🎉 Processed {len(processed_mentors)} NEW mentors from current page")
    return processed_mentors, already_processed

def aggressive_scroll_to_load_mentors(page):
    """Aggressive scroll method - scroll 2 times to 100% of page to load all mentors"""
    try:
        print("🚀 AGGRESSIVE SCROLL: Scrolling 2 times to 100% of page...")
        
        # Get current number of mentor cards
        current_mentors = page.locator("div.card-align").count()
        print(f"📊 Current mentors before aggressive scroll: {current_mentors}")
        
        # Scroll 2 times to 100% of page height
        for i in range(2):
            print(f"📜 Aggressive scroll {i+1}/2...")
            
            try:
                # Scroll to 100% of page height
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(1000)  # Wait 1 second between scrolls
                
                # Check if new mentors were loaded
                new_mentors = page.locator("div.card-align").count()
                if new_mentors > current_mentors:
                    print(f"✅ Found {new_mentors - current_mentors} new mentors during scroll {i+1}!")
                    current_mentors = new_mentors
                    
            except Exception as scroll_error:
                print(f"⚠️  Error during scroll {i+1}: {scroll_error}")
                # Continue with next scroll attempt
                continue
        
        # Final check
        try:
            final_mentors = page.locator("div.card-align").count()
            total_new_mentors = final_mentors - current_mentors
            
            if total_new_mentors > 0:
                print(f"🎉 AGGRESSIVE SCROLL SUCCESS: Loaded {total_new_mentors} new mentors!")
                return True
            else:
                print("⚠️  Aggressive scroll completed - no new mentors found")
                return False
        except Exception as final_error:
            print(f"⚠️  Error in final check: {final_error}")
            return False
            
    except Exception as e:
        print(f"❌ Error during aggressive scroll: {e}")
        return False

def scroll_to_load_more_mentors(page):
    """Optimized scroll function to load more mentors efficiently"""
    try:
        print("📜 Scrolling to load more mentors...")
        
        # Get current number of mentor cards
        current_mentors = page.locator("div.card-align").count()
        print(f"📊 Current mentors on page: {current_mentors}")
        
        # Use more efficient scrolling - scroll in steps to trigger lazy loading
        page_height = page.evaluate("document.body.scrollHeight")
        current_scroll = page.evaluate("window.pageYOffset")
        
        # Scroll in increments to trigger loading
        for scroll_step in [0.7, 0.85, 1.0]:
            scroll_position = int(page_height * scroll_step)
            page.evaluate(f"window.scrollTo(0, {scroll_position})")
            page.wait_for_timeout(800)  # Shorter wait between scrolls
            
            # Check if new content loaded
            new_mentors = page.locator("div.card-align").count()
            if new_mentors > current_mentors:
                print(f"✅ Loaded {new_mentors - current_mentors} new mentors!")
                return True
        
        # Final check
        final_mentors = page.locator("div.card-align").count()
        if final_mentors > current_mentors:
            print(f"✅ Loaded {final_mentors - current_mentors} new mentors!")
            return True
        else:
            print("⚠️  No new mentors loaded - may have reached the end")
            return False
            
    except Exception as e:
        print(f"❌ Error scrolling to load more mentors: {e}")
        return False

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

def scrape_linuxfoundation(page, url, browser, existing_names=None):
    """Extract information from Linux Foundation Mentorship site using Playwright"""
    global scraped_data, stop_scraping
    
    print(f"🚀 Loading Linux Foundation Mentorship directly: {url}")
    
    if existing_names:
        print(f"🔄 Will skip {len(existing_names)} existing mentors")
    
    # Clear scraped data at start
    scraped_data = []
    stop_scraping = False
    
    # Navigate to the URL with Playwright
    try:
        print("📍 Navigating to Linux Foundation Mentorship...")
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
        
        # Verify we're on Linux Foundation Mentorship
        if "mentorship.lfx.linuxfoundation.org" in current_url:
            print("✅ Confirmed: On Linux Foundation Mentorship website!")
        else:
            print(f"⚠️  Warning: Not on Linux Foundation Mentorship page. Current URL: {current_url}")
            
    except Exception as e:
        print(f"❌ Error loading Linux Foundation Mentorship: {e}")
        raise Exception(f"Failed to load Linux Foundation Mentorship: {e}")
    
    # Additional wait to ensure page is fully loaded and mentor cards appear (optimized)
    print("⏳ Waiting for mentor cards to appear...")
    try:
        # Wait for at least one mentor card to appear with shorter timeout
        page.wait_for_selector("div.card-align", timeout=15000)
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
        mentor_cards = page.locator("div.card-align").count()
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
    
    print("📜 Starting scroll-based mentor loading...")
    if MAX_MENTORS > 0:
        print(f"🎯 Target: Collecting {MAX_MENTORS} NEW mentors (skipping existing ones)")
    else:
        print("🎯 Target: Collecting all available NEW mentors")
    
    scroll_count = 0
    max_scrolls = 50  # Safety limit for scrolling
    new_mentors_found = len(initial_mentors)
    
    while scroll_count < max_scrolls and not stop_scraping:
        try:
            # Check if user wants to stop
            if stop_scraping:
                print("🛑 Stop signal received! Saving progress...")
                break
            
            # Try to scroll to load more mentors
            scroll_success = scroll_to_load_more_mentors(page)
            
            if not scroll_success:
                print("📜 Regular scroll failed, trying aggressive scroll...")
                # Try aggressive scroll as fallback
                aggressive_success = aggressive_scroll_to_load_mentors(page)
                
                if not aggressive_success:
                    print("📜 No more mentors to load. Reached the end of the list.")
                    break
            
            scroll_count += 1
            
            # Minimal wait time since we don't need to scroll back anymore
            page.wait_for_timeout(200)
            
            # Process the newly loaded mentors
            print(f"🔍 Processing new mentors after scroll {scroll_count}...")
            new_mentors, already_processed = process_mentors_on_page(page, browser, existing_names, already_processed)
            scraped_data.extend(new_mentors)
            new_mentors_found += len(new_mentors)
            
            print(f"📊 Total mentors processed so far: {new_mentors_found}")
            
            # Check if we've reached our target
            if MAX_MENTORS > 0 and new_mentors_found >= MAX_MENTORS:
                print(f"✅ Reached target of {MAX_MENTORS} mentors! Stopping...")
                break
            
            # If no new mentors were found in this scroll, we might have reached the end
            if len(new_mentors) == 0:
                print("⚠️  No new mentors found in this scroll. Checking if we've reached the end...")
                # Try one more scroll to make sure we haven't reached the end
                page.wait_for_timeout(500)
                continue
            
        except Exception as e:
            print(f"❌ Error during scroll {scroll_count}: {e}")
            print("Continuing with next scroll...")
            page.wait_for_timeout(3000)
            continue
    
    if scroll_count >= max_scrolls:
        print(f"Maximum scroll limit reached ({max_scrolls}). Stopping to prevent infinite loop.")
    
    # Check if stopped by user
    if stop_scraping:
        print("🛑 Scraping stopped by user. Extracting and saving current progress...")
        
        # Extract mentors that are currently visible on the page
        print("Parse kardan-e HTML-e jari...")
        soup = BeautifulSoup(page.content(), 'html.parser')
        
        MENTOR_CARD_SELECTOR = "div.card-align"
        mentor_cards = soup.select(MENTOR_CARD_SELECTOR)
        
        print(f"Tedad-e nahayi {len(mentor_cards)} mentor peyda shod. Dar hale estekhraj...")
        
        # Filter out existing mentors and apply limit
        new_mentors = []
        for card in mentor_cards:
            name_element = card.select_one("a.card-title span")
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
            name_element = card.select_one("a.card-title span")
            name = name_element.text.strip() if name_element else "N/A"
            
            # Extract project information from the card
            projects = []
            project_elements = card.select("div.icons-container img[title]")
            for project_element in project_elements:
                project_title = project_element.get('title')
                if project_title:
                    projects.append(project_title)
            
            # Separate projects and mentees
            project_data = ", ".join(projects) if projects else "N/A"
            separated_data = separate_projects_and_mentees(project_data)
            
            row = {
                "Name": name,
                "Profile Link": "N/A",  # Will be filled from profile page
                "Projects": separated_data["projects"],
                "Mentees": separated_data["mentees"],
                "Social Links": "N/A",  # Will be filled from profile page
                "User Features": "N/A"  # Will be filled from profile page
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
    
    MENTOR_CARD_SELECTOR = "div.card-align"
    
    mentor_cards = soup.select(MENTOR_CARD_SELECTOR)
    
    data = []
    print(f"Tedad-e nahayi {len(mentor_cards)} mentor peyda shod. Dar hale estekhraj...")

    # Filter out existing mentors and apply limit
    new_mentors = []
    for card in mentor_cards:
        name_element = card.select_one("a.card-title span")
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
        name_element = card.select_one("a.card-title span")
        name = name_element.text.strip() if name_element else "N/A"
        
        # Extract project information from the card
        projects = []
        project_elements = card.select("div.icons-container img[title]")
        for project_element in project_elements:
            project_title = project_element.get('title')
            if project_title:
                projects.append(project_title)
        
        # Separate projects and mentees
        project_data = ", ".join(projects) if projects else "N/A"
        separated_data = separate_projects_and_mentees(project_data)
        
        row = {
            "Name": name,
            "Profile Link": "N/A",  # Will be filled from profile page
            "Projects": separated_data["projects"],
            "Mentees": separated_data["mentees"],
            "Social Links": "N/A",  # Will be filled from profile page
            "User Features": "N/A"  # Will be filled from profile page
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
    
    print("--- Linux Foundation Mentorship Scraper (v23 - Updated for LFX) ---")
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
        # Start browser in headless mode for Linux Foundation
        print("🚀 Starting Playwright with Chromium (headless mode)...")
        browser, page, playwright = get_browser_and_page(headless=True)
        
        current_browser = browser  # Set global browser for interrupt handling
        
        # Debug: Show initial state
        print("🔍 Initial browser state:")
        print(f"   Current URL: {page.url}")
        print(f"   Page Title: {page.title()}")
        
        # Check user agent
        user_agent = page.evaluate("navigator.userAgent")
        print(f"   User Agent: {user_agent}")
        
        # No session restoration needed for Linux Foundation
        
        # Add initial delay to let user see the browser window
        print("\n⏰ Browser opened! Waiting 5 seconds for you to see the window...")
        time.sleep(5)
        
        # Check if we can access the page
        page_accessible = check_login_status(page)
        
        if not page_accessible:
            print("❌ Cannot access Linux Foundation Mentorship page. Please check the URL and try again.")
            return
        else:
            print("✅ Linux Foundation Mentorship page accessible! Proceeding with scraping...")
        
        print("🎯 Starting scraping in HEADLESS background mode...")
        result_data = scrape_linuxfoundation(page, URL, browser, existing_names)
        
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
