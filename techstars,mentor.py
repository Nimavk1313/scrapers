import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

# --- Tanzimat-e Avvalieh ---
URL = "https://www.techstars.com/mentors"
OUTPUT_FILENAME = "techstars_mentors"
PROFILE_LIMIT = 3500 

def get_driver():
    """Rah-andazi va bazgardandan-e driver Selenium"""
    options = webdriver.ChromeOptions()
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
    options.add_argument("--start-maximized")
    options.add_argument("--disable-gpu")
    
    service = ChromeService(executable_path=ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    return driver

def scrape_techstars(driver, url):
    """Estekhraj-e etela'at az site-e Techstars"""
    print(f"Dar hale load kardan-e site: {url}...")
    driver.get(url)
    time.sleep(5) 

    MENTOR_CARD_SELECTOR_CSS = "div.jss193.jss14.jss196.jss234.jss246.jss259"
    MENTOR_CARD_SELECTOR_BY = (By.CSS_SELECTOR, MENTOR_CARD_SELECTOR_CSS)
    
    print(f"Shروع scroll kardan ta residan be {PROFILE_LIMIT} profile ya payan-e safhe...")
    last_known_count = -1
    stall_counter = 0 
    while True:
        current_profile_count = len(driver.find_elements(*MENTOR_CARD_SELECTOR_BY))
        print(f"Tedad-e profile-haye peyda shode: {current_profile_count} az {PROFILE_LIMIT}")

        if current_profile_count >= PROFILE_LIMIT:
            print(f"Be had-e {PROFILE_LIMIT} profile residim. Motovaghef mishavad.")
            break
        
        if current_profile_count == last_known_count:
            stall_counter += 1
            print(f"Tedad-e profile-ha taghir nakard. Shomaresh-e tavaqof: {stall_counter}/3")
        else:
            stall_counter = 0
        
        if stall_counter >= 3:
            print("Mentor-e jadidi baraye 3 talash-e motavali peyda nashod. Scroll be payan resid.")
            break
        
        last_known_count = current_profile_count
        
        # <<<<<<< TAGHIR-E JADID: SCROLL BE PAIIN VA SEPAS KAMI BE BĀLĀ >>>>>>>
        # 1. Anjam-e scroll be entehaye safhe
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1) # Takhir-e kutah

        # 2. Anjam-e scroll-e kuchak be samte bālā
        driver.execute_script("window.scrollBy(0, -350);")
        
        # 3. Sabr kardan baraye load shodan-e content-e jadid
        time.sleep(5)

    print("Parse kardan-e HTML-e nahayi...")
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    
    mentor_cards = soup.select(MENTOR_CARD_SELECTOR_CSS)
    
    NAME_SELECTOR = "h6.jss138.jss17.jss169.jss180"
    TITLE_SELECTOR = "p.jss138.jss16.jss171.jss182"
    SOCIAL_LINK_SELECTOR = "a.jss18"
    
    data = []
    print(f"Tedad-e nahayi {len(mentor_cards)} mentor peyda shod. Dar hale estekhraj...")

    for card in mentor_cards:
        name = card.select_one(NAME_SELECTOR).text.strip() if card.select_one(NAME_SELECTOR) else "N/A"
        title = card.select_one(TITLE_SELECTOR).text.strip() if card.select_one(TITLE_SELECTOR) else "N/A"
        
        social_links_elements = card.select(SOCIAL_LINK_SELECTOR)
        social_links = [link['href'] for link in social_links_elements if link.has_attr('href')]
        social_links_text = ', '.join(social_links)

        data.append({"Name": name, "Title": title, "Social Links": social_links_text})

    return data

def save_data(data, filename):
    """Zakhire kardan-e dadeha dar format-haye CSV va JSON"""
    if not data:
        print("Hich dade-i baraye zakhire kardan peyda nashod.")
        return

    df = pd.DataFrame(data)
    csv_path = f"{filename}.csv"
    df.to_csv(csv_path, index=False, encoding='utf-8-sig')
    print(f"✅ Etela'at ba movafaghiat dar file {csv_path} zakhire shod.")

    json_path = f"{filename}.json"
    df.to_json(json_path, orient='records', indent=4, force_ascii=False)
    print(f"✅ Etela'at ba movafaghiat dar file {json_path} zakhire shod.")

def main():
    """Tabe-ye asli baraye ejraye barnameh"""
    print("--- Techstars Mentor Scraper (v33 - Up/Down Scroll) ---")
    
    driver = None
    try:
        driver = get_driver()
        scraped_data = scrape_techstars(driver, URL)
        save_data(scraped_data, OUTPUT_FILENAME)
    
    except Exception as e:
        print(f"Yek moshkel-e kolli pish amad: {e}")
        
    finally:
        if driver:
            driver.quit()
            print("Mororgar baste shod.")

if __name__ == "__main__":
    main()
