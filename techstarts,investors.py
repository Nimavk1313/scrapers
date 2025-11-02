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
URL = "https://www.techstars.com/portfolio"
OUTPUT_FILENAME = "techstars_portfolio"
# <<<<<<< HAD-E TE'DAD-E COMPANY-HA RA INJA TA'YIN KONID >>>>>>>
COMPANY_LIMIT = 5050 

def get_driver():
    """Rah-andazi va bazgardandan-e driver Selenium"""
    options = webdriver.ChromeOptions()
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
    options.add_argument("--start-maximized")
    options.add_argument("--disable-gpu")
    
    service = ChromeService(executable_path=ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    return driver

def scrape_portfolio(driver, url):
    """Estekhraj-e etela'at az bakhsh-e portfolio-e Techstars"""
    print(f"Dar hale load kardan-e site: {url}...")
    driver.get(url)
    time.sleep(5) 

    # Selector-haye pishnahadi-e shoma
    COMPANY_CARD_SELECTOR_CSS = "div.jss612.CompanyCard.jss1177.jss614.jss638"
    COMPANY_CARD_SELECTOR_BY = (By.CSS_SELECTOR, COMPANY_CARD_SELECTOR_CSS)
    
    print(f"Shروع scroll kardan ta residan be {COMPANY_LIMIT} company ya payan-e safhe...")
    last_known_count = -1
    stall_counter = 0 
    while True:
        current_company_count = len(driver.find_elements(*COMPANY_CARD_SELECTOR_BY))
        print(f"Tedad-e company-haye peyda shode: {current_company_count} az {COMPANY_LIMIT}")

        if current_company_count >= COMPANY_LIMIT:
            print(f"Be had-e {COMPANY_LIMIT} company residim. Motovaghef mishavad.")
            break
        
        if current_company_count == last_known_count:
            stall_counter += 1
            print(f"Tedad-e company-ha taghir nakard. Shomaresh-e tavaqof: {stall_counter}/3")
        else:
            stall_counter = 0
        
        if stall_counter >= 3:
            print("Company-e jadidi baraye 3 talash-e motavali peyda nashod. Scroll be payan resid.")
            break
        
        last_known_count = current_company_count
        
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1)
        driver.execute_script("window.scrollBy(0, -350);")
        time.sleep(5)

    print("Parse kardan-e HTML-e nahayi...")
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    
    company_cards = soup.select(COMPANY_CARD_SELECTOR_CSS)
    
    NAME_SELECTOR = "span.jss1178"
    DESCRIPTION_SELECTOR = "p.jss723.jss1181.jss758.jss769"
    WEBSITE_SELECTOR = "a.jss1186"
    SOCIAL_LINKS_CONTAINER_SELECTOR = "div.jss612.jss1188.jss615.jss659.jss667"
    
    data = []
    print(f"Tedad-e nahayi {len(company_cards)} company peyda shod. Dar hale estekhraj...")

    for card in company_cards:
        name = card.select_one(NAME_SELECTOR).text.strip() if card.select_one(NAME_SELECTOR) else "N/A"
        description = card.select_one(DESCRIPTION_SELECTOR).text.strip() if card.select_one(DESCRIPTION_SELECTOR) else "N/A"
        website = card.select_one(WEBSITE_SELECTOR)['href'] if card.select_one(WEBSITE_SELECTOR) and card.select_one(WEBSITE_SELECTOR).has_attr('href') else "N/A"
        
        # Estekhraj-e hame-ye link-ha az dakhel-e container-e anha
        social_links_container = card.select_one(SOCIAL_LINKS_CONTAINER_SELECTOR)
        if social_links_container:
            social_links_elements = social_links_container.select("a")
            social_links = [link['href'] for link in social_links_elements if link.has_attr('href')]
            social_links_text = ', '.join(social_links)
        else:
            social_links_text = "N/A"

        data.append({
            "Name": name, 
            "Description": description, 
            "Website": website, 
            "Social Links": social_links_text
        })

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
    print("--- Techstars Portfolio Scraper (v1) ---")
    
    driver = None
    try:
        driver = get_driver()
        scraped_data = scrape_portfolio(driver, URL)
        save_data(scraped_data, OUTPUT_FILENAME)
    
    except Exception as e:
        print(f"Yek moshkel-e kolli pish amad: {e}")
        
    finally:
        if driver:
            driver.quit()
            print("Mororgar baste shod.")

if __name__ == "__main__":
    main()
