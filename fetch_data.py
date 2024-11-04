import os
import requests
import csv 
import logging
import re

from datetime import datetime
from dotenv import load_dotenv


# Load env variables 
load_dotenv()

# Logging
log_filename = "fetch_data_log.log"
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[logging.FileHandler(log_filename), logging.StreamHandler()])

def fetch_data(url, data_type):
    """
    Fetch data from the Spare API and return as a list of dict.
    """
    token = os.getenv('SPARELABS_API_TOKEN')
    if not token:
        raise ValueError("API token is missing, set the token in the .env file.")

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
            logging.error(f"Failed to fetch {data_type} data: {response.status_code} - {response.text}")
            response.raise_for_status()
        
        data = response.json()
        if not data or 'data' not in data:
            break
        
        all_data.extend(data['data'])

        # Log progress
        logging.info(f"Fetched {len(all_data)} {data_type} so far...")

        # If there are less than 50 records in the response, it means all data is fetched
        if len(data['data']) < 50:
            break

        page += 1

    logging.info(f"Fetched {len(all_data)} {data_type}.")
    return {'data': all_data}

def format_phone_number(phone_number):
    """
    Format the phone number to (XXX)XXX-XXXX format instead of 1204XXXXXXX.
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

def save_to_csv(data, filename, columns, process_row,folder):
    """
    Save the data to a CSV file.
    """
    if not os.path.exists(folder):
        os.makedirs(folder)

    file_path = os.path.join(folder, filename)

    with open(file_path, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(columns)
        
        for item in data["data"]:
            row = process_row(item)
            if row:
                writer.writerow(row)
    logging.info(f"Data successfully saved to {file_path}")

def process_rider_row(rider):
    """
    Process a single rider row for CSV.
    """
    logging.info(f"Processing rider: {rider.get('externalNumericId', 'N/A')}")
    metadata = rider.get('metadata', {})
    
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
    logging.debug(f"Generated row: {row}")
    return row

def process_driver_row(driver):
    """
    Process a single driver row for CSV.
    """
    metadata = driver.get('metadata', {})
    row = [
    metadata.get("wtp_driver_id", ""),
    driver.get("firstName", ""),
    driver.get("lastName", "")
    ]
    return row

def clean_description(text):

    text = re.sub(r'\s*\(.*?\)', '', text).strip()
    
    text = text.split(';')[0].strip()
    return text


def process_vehicle_row(vehicle):
    """
    Process a single vehicle row for CSV.
    """
    metadata = vehicle.get('metadata', {})

    identifier = vehicle.get("identifier", "")
    identifier = identifier.split()[0]  # Keep only the first part of the identifier

    make = clean_description(vehicle.get("make", ""))
    model = clean_description(vehicle.get("model", ""))
    description = clean_description(metadata.get("vehicle_description", ""))

    row = [
        identifier,
        metadata.get("contractor_name", ""),
        vehicle.get("licensePlate", ""),
        vehicle.get("color", ""),
        make,
        model,
        description
    ]
    return row


def main():
    try:
        logging.info("Starting to fetch data...")
        current_date = datetime.now().strftime("%Y-%m-%d")
        folder = f"data_csv_{current_date}" 

        # Fetch Riders
        riders_url = "https://api.sparelabs.com/v1/riders"
        riders_data = fetch_data(riders_url, 'riders')
        riders_filename = f"riders_v1{current_date}.csv"
        rider_columns = [
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
        save_to_csv(riders_data, riders_filename, rider_columns, process_rider_row,folder)
        
        # Fetch Drivers
        drivers_url = "https://api.sparelabs.com/v1/drivers"
        drivers_data = fetch_data(drivers_url, 'drivers')
        drivers_filename = f"drivers_{current_date}.csv"
        driver_columns = [
            "Internal Driver ID",
            "First Name",
            "Last Name"
        ]
        save_to_csv(drivers_data, drivers_filename, driver_columns, process_driver_row,folder)
        
        # Fetch Vehicles
        vehicles_url = "https://api.sparelabs.com/v1/vehicles"
        vehicles_data = fetch_data(vehicles_url, 'vehicles')
        vehicles_filename = f"vehicles_{current_date}.csv"
        vehicle_columns = [
            "Vehicle ID",
            "Contractor Name",	
            "License Plate",	
            "Color",	
            "Make",	
            "Model",
            "Vehicle Description"
        ]
        save_to_csv(vehicles_data, vehicles_filename, vehicle_columns, process_vehicle_row,folder)
        
        logging.info("Data processing and upload completed successfully.")
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching data: {e}")
    except Exception as e:
        logging.error(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
