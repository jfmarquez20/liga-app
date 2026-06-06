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
import traceback

def handler(event, context):
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
    email, password, court = get_variables_from_s3("juan-s3-general", "variables.json")

    if event.get('request', {}).get('type') == 'IntentRequest':
            intent_name = event['request']['intent']['name']
            print(event['request']['intent']['slots'])
            if intent_name == 'courtSchedule':
                court_name = event['request']['intent']['slots']['court']['value'].lower()
                date = event['request']['intent']['slots']['day']['value']
                time = event['request']['intent']['slots']['time']['value']

                if not date:
                    return build_alexa_response("Mani habla bien, no te entendí el día")
                if not court_name:
                    return build_alexa_response("Mani habla bien, no te entendí la cancha")
                if not time:
                    return build_alexa_response("Mani habla bien, no te entendí la hora")

                COURT_MAP = {
                    "parque de raquetas 1": "Parque de Raquetas 1",
                    "parque de raquetas 2": "Parque de Raquetas 2",
                    "parque de raquetas 3": "Parque de Raquetas 3",
                    "el golf 1": "El Golf 1",
                    "el golf 2": "El Golf 2",
                }

                target_court = COURT_MAP.get(court_name)
                target_date = date + "/60/"

                court = f"//div[contains(@class,'shadow') and .//h4[text()='{target_court}']]//a[contains(@href,'/{time}/60/')]"
                run_booking_alexa(driver, target_date, court)
                return build_alexa_response("Listo compae. Sale tenisito")
            else:
                return build_alexa_response("Mani pasó algo. Revisa tu manualmente pa ve")
    else:
            # Called from EventBridge
            today_date = datetime.now(ZoneInfo("America/Bogota"))
            target_date = (today_date + timedelta(days=3)).strftime('%Y-%m-%d') + "/60/"
            run_booking_scheduler(driver, email, password, target_date, court)


def run_booking_scheduler(driver, email, password, target_date, court):
    try:
        login(driver, email, password)

        while True:
            current_time = datetime.now(ZoneInfo("America/Bogota")).hour
            if current_time >= 12:
                time.sleep(0.15)
                driver.refresh()
                break
        
        print("Start booking...")
        book_court(driver, target_date, court)
        
        return {"statusCode": 200, "body": "Script executed properly"}

    except Exception as e:
        print(f"Handler error: {e}")
        raise

    finally:
        driver.quit()


def run_booking_alexa(driver, target_date, court):
    try:
        email = "jfme050@gmail.com"
        password = "1010105554"
        login(driver, email, password)
        book_court(driver, target_date, court)
        
        return {"statusCode": 200, "body": "Script executed properly"}

    except Exception as e:
        print(f"Handler error: {e}")
        raise

    finally:
        driver.quit()


def build_alexa_response(message):
    return {
        "version": "1.0",
        "response": {
            "outputSpeech": {
                "type": "PlainText",
                "text": message
            },
            "shouldEndSession": True
        }
    }

def get_variables_from_s3(bucket, key):
    s3 = boto3.client("s3")
    response = s3.get_object(Bucket=bucket, Key=key)
    content = response['Body'].read().decode('utf-8')
    data = json.loads(content)
    return data['email'], data['password'], data['court']

def login(driver, email_value, password_value):
    driver.get("https://reservadeportes.com/LigaTenisAtlantico.html")
    try:
        email = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "email")))
        email.send_keys(email_value)
        
        password = driver.find_element(By.NAME, "password")
        password.send_keys(password_value)
        
        button_submit = driver.find_element(By.XPATH, "//button[@type='submit']")
        button_submit.click()
        print(f'Logged in succesfully using {email_value} as username')
    
    except Exception as e:
        print(f"Login error: {e}")

def book_court(driver, target_date, court):
    try:
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