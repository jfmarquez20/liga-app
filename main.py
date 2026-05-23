from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import time
import boto3

def handler(event, context):
    today_date = datetime.now(ZoneInfo("America/Bogota"))
    target_date = (today_date + timedelta(days=2)).strftime('%Y-%m-%d') + "/60/"
    url = "https://reservadeportes.com/LigaTenisAtlantico.html"

    chrome_options = Options()
    chrome_options.binary_location = "/opt/chrome/chrome"
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-dev-tools")
    chrome_options.add_argument("--no-zygote")
    chrome_options.add_argument("--single-process")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--user-data-dir=/tmp/chrome-user-data")
    chrome_options.add_argument("--remote-debugging-port=9222")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")

    service = Service(executable_path="/opt/chromedriver")
    driver = webdriver.Chrome(service=service, options=chrome_options)

    login(driver)

    while True:
        current_time = datetime.now(ZoneInfo("America/Bogota")).hour
        if current_time >= 9:
            time.sleep(0.15)
            driver.refresh()
            break
    
    print("Start booking...")
    book_court(driver, target_date)
    title= driver.title
    driver.quit()

    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "title": title
            }
        ),
    }

def get_variables_from_s3(bucket, key):
    s3 = boto3.client("s3")
    response = s3.get_object(Bucket=bucket, Key=key)
    content = response['Body'].read().decode('utf-8')
    data = json.loads(content)
    return data['email'], data['password'], data['court']

def login(driver):
    driver.get("https://reservadeportes.com/LigaTenisAtlantico.html")
    try:
        email_value, password_value, court = get_variables_from_s3("juan-s3-general", "variables.json")
        email = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "email")))
        email.send_keys(email_value)
        
        password = driver.find_element(By.NAME, "password")
        password.send_keys(password_value)
        
        button_submit = driver.find_element(By.XPATH, "//button[@type='submit']")
        button_submit.click()
        print(f'Logged in succesfully using {email_value} as username')
    
    except Exception as e:
        print(f"Login error: {e}")

def book_court(driver, target_date):
    try:
        email, password, court = get_variables_from_s3("juan-s3-general", "variables.json")
        driver.get(f"https://reservadeportes.com/calendario/LigaTenisAtlantico/1/{target_date}")
        print(target_date)

        WebDriverWait(driver, 10).until(
            lambda d: len(
            d.find_elements(By.CSS_SELECTOR, "a.slot-btn.btn-success")
            ) > 0
        )
        
        court_link = driver.find_element(By.XPATH, court)
        print(court_link.get_attribute('href'))
        driver.get(court_link.get_property('href'))

        checkbox = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//html/body/main/div[2]/div/div/div/form/p[2]/label/input"))
        )
        driver.execute_script("arguments[0].scrollIntoView(true);", checkbox)
        time.sleep(0.4)
        checkbox.click()
        
        submit_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "/html/body/main/div[2]/div/div/div/div/button"))
        )
        driver.execute_script("arguments[0].scrollIntoView(true);", submit_button)
        time.sleep(0.7)
        submit_button.click()
        time.sleep(2)
        
        try:
            status = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, "/html/body/main/div[3]/div/div/div/form/center/h1/div")))
            print(status.text)
        except:
            print("Booking completed!")

    except Exception as e:  
        print(f"Booking error: {e}")