import os
import requests
import csv 
import logging
from datetime import datetime
from dotenv import load_dotenv

from office365.runtime.auth.user_credential import UserCredential
from office365.sharepoint.client_context import ClientContext

#load env variables 
load_dotenv()

# logging
log_filename = "fetch_riders_log.log"
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[logging.FileHandler(log_filename), logging.StreamHandler()])

def fetch_riders_data():
    """
    Fetch rider data from the Spare API and return as a list of dict.
    """
    token = os.getenv('SPARELABS_API_TOKEN')
    if not token:
        raise ValueError("API token is missing, set the token in the .env file.")

    # run local for token
    # script_dir = os.path.dirname(os.path.abspath(__file__))
    # token_file_path = os.path.join(script_dir, 'token.txt')
    
    # with open(token_file_path, 'r') as f:
    #     token = f.read().strip() 

    url = "https://api.sparelabs.com/v1/riders"
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }

    all_data = []

    # Fetch data page by page until all data is retrieved
    page = 1
    while True:
        params = {'limit': 50, 'skip': (page - 1) * 50}
        response = requests.get(url, headers=headers, params=params)
        if response.status_code != 200:
            logging.error(f"Failed to fetch data: {response.status_code} - {response.text}")
            response.raise_for_status()
        
        data = response.json()
        if not data or 'data' not in data:
            break
        
        all_data.extend(data['data'])

        # Log progress fetch riders
        logging.info(f"Fetched {len(all_data)} riders so far...")


        # If there are less than 50 records in the response, it means all data is fetched
        if len(data['data']) < 50:
            break

        page += 1

    logging.info(f"Fetched {len(all_data)} riders.")
    return {'data': all_data}
    # return {'data': all_data[:limit]}


def format_phone_number(phone_number):
    """
    Format the phone number to (XXX)XXX-XXXX format instead if 1204XXXXXXX.
    """
    if not phone_number:
        return ""

    phone_number = phone_number.replace("+", "").replace("-", "").replace(" ", "")
    if len(phone_number) == 11 and phone_number.startswith("1"):
        phone_number = phone_number[1:]
    if len(phone_number) == 10:
        area_code = phone_number[:3]
        prefix = phone_number[3:6]
        line_number = phone_number[6:]
        return f"({area_code}){prefix}-{line_number}"
    return phone_number


def save_to_csv(data, filename):
    """
    Save the Spare rider data to a CSV file.
    """
    columns = [
        "Registration Number", 
        "First Name", 
        "Last Name", 
        "Telephone", 
        "Telephone Ext", 
        "Email", 
        "Mailing Address", 
        "City/Town", 
        "Province/State", 
        "Postal/Zip Code"
    ]

    with open(filename, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(columns)
        
        for rider in data["data"]:
            logging.info(f"Processing rider: {rider.get('externalNumericId', 'N/A')}")
            metadata = rider.get('metadata', {})
            if not metadata:
                logging.warning(f"No metadata found for rider: {rider}")
                continue
            
            logging.debug(f"Rider metadata: {metadata}")

            mailing_address_unit = metadata.get('mailing_address_unit', '')
            mailing_address = metadata.get('mailing_address', '')
            full_mailing_address = f"{mailing_address_unit}-{mailing_address}" if mailing_address_unit else mailing_address

            if not full_mailing_address:
                logging.warning(f"Incomplete address information for rider: {rider}")
            
            phone_number = format_phone_number(rider.get("phoneNumber", ""))

            row = [
                rider.get("externalNumericId", ""),
                rider.get("firstName", ""),
                rider.get("lastName", ""),
                phone_number,
                "",  # Telephone Ext (empty column)
                rider.get("email", ""),
                full_mailing_address,
                metadata.get("mailing_city", ""),
                metadata.get("mailing_province_state", ""),
                metadata.get("mailing_postal_zip_code", "")
            ]
            writer.writerow(row)
    logging.info(f"Data successfully saved to {filename}")


def upload_to_sharepoint(filename):
    """
    Upload the CSV file to SharePoint.
    """
    sharepoint_url = os.getenv('https://winnipeghc.sharepoint.com')
    sharepoint_user = os.getenv('pcardosopacheco@winnipeg.ca')
    sharepoint_password = os.getenv('SHAREPOINT_PASSWORD')
    sharepoint_folder = "https://winnipeghc.sharepoint.com/:f:/s/ISPPortfolioandProjects/EkqfoGn_5q5LuDLx5uo_0-QB_luex3NhDDcmEKXUUxIVqw?e=aRxNyv"  


    ctx = ClientContext(sharepoint_url).with_credentials(UserCredential(sharepoint_user, sharepoint_password))
    with open(filename, 'rb') as content_file:
        file_content = content_file.read()
        target_folder = ctx.web.get_folder_by_server_relative_url(sharepoint_folder)
        target_folder.upload_file(filename, file_content).execute_query()
    
    logging.info(f"File {filename} uploaded to SharePoint successfully.")


def main():
    try:
        logging.info("Starting to fetch rider data...")
        riders_data = fetch_riders_data()

        # riders_data = fetch_riders_data(limit=30)
        current_date = datetime.now().strftime("%Y-%m-%d")
        filename = f"riders_{current_date}.csv"
        save_to_csv(riders_data, filename)
        print(f"Data successfully saved to {filename}")


    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching riders data: {e}")
    except Exception as e:
        logging.error(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
