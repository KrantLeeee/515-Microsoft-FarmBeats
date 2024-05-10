import os
import time
import cv2
import board
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
from azure.storage.blob import BlobServiceClient
from azure.data.tables import TableServiceClient
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Azure Blob Storage and Table Storage clients
connect_str = os.getenv("connection_string")
blob_service_client = BlobServiceClient.from_connection_string(connect_str)
container_name = 'devicetest01'

# Azure Table Storage setup
table_service = TableServiceClient.from_connection_string(connect_str)
table_name = 'DeviceTest01'
table_client = table_service.get_table_client(table_name)

# Ensure the table exists, create if not
try:
    table_client.create_table()
except Exception as e:
    print("Table already exists or another error occurred:", e)

# Function to upload a file to Azure Blob Storage and store metadata in Azure Table Storage
def upload_file_and_save_metadata(file_path, description, weevil_count):
    blob_client = blob_service_client.get_blob_client(container=container_name, blob=os.path.basename(file_path))

    # Upload the image
    with open(file_path, "rb") as data:
        blob_client.upload_blob(data, overwrite=True)

    # Get the blob URL
    blob_url = blob_client.url

    # Current timestamp in ISO 8601 format
    timestamp = datetime.utcnow().isoformat() + 'Z'

    # Insert or merge the new entity into the table
    metadata = {
        'PartitionKey': 'ImageDescription',
        'RowKey': os.path.basename(file_path),
        'Description': description,
        'ImageUrl': blob_url,
        'FileName': os.path.basename(file_path),
        'TS': timestamp,
        'Weevil_number': weevil_count
    }
    table_client.upsert_entity(entity=metadata)

    return blob_url, metadata

# Function to capture images using Raspberry Pi's camera
def capture_image():
    save_path = os.getenv("save_path")
    os.makedirs(save_path, exist_ok=True)
    
    filename = os.path.join(save_path, time.strftime("%Y%m%d-%H%M%S") + ".jpg")
    command = f"libcamera-still -o '{filename}' --autofocus-mode auto --tuning-file /usr/share/libcamera/ipa/rpi/vc4/imx477_af.json"
    print("Executing command:", command)
    os.system(command)
    
    if os.path.exists(filename) and os.path.isfile(filename):
        print(f"Captured {filename}")
        image = cv2.imread(filename)
        if image is not None:
            count = process_image(image)
            description = f"Time: {time.strftime('%H:%M:%S')}\nPest category: Weevil\nNumber: {count}"
            upload_file_and_save_metadata(filename, description, count)
            print(f"Processed and uploaded {filename}: {count} weevils found")
        else:
            print(f"Failed to load image {filename}")

# Function to crop an image to a centered square
def crop_center_square(image):
    height, width = image.shape[:2]
    central_square_side = min(height, width)
    top = (height - central_square_side) // 2
    left = (width - central_square_side) // 2
    cropped_img = image[top:top + central_square_side, left:left + central_square_side]
    return cropped_img

# Function to process an image and count the weevils
def process_image(image):
    cropped_image = crop_center_square(image)
    gray = cv2.cvtColor(cropped_image, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 80, 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    min_area = 45000  # Minimum area to be considered a weevil
    max_area = 145000  # Maximum area to be considered a weevil
    weevil_count = 0

    for contour in contours:
        area = cv2.contourArea(contour)
        if min_area < area < max_area:
            weevil_count += 1

    processed_filename = os.path.join(os.getenv("save_path"), "processed_" + time.strftime("%Y%m%d-%H%M%S") + ".jpg")
    cv2.imwrite(processed_filename, thresh)
    return weevil_count

# Function to calculate distance from sensor voltage
def get_distance(voltage):
    k = 12
    ep = 0.05
    distance = k / (voltage + ep)

    if distance < 4:
        distance = 4
    elif distance > 30:
        distance = 30
    return distance

# Initialize I2C interface and ADS1115
i2c = busio.I2C(board.SCL, board.SDA)
ads = ADS.ADS1115(i2c)

# Define the analog input channels
channel1 = AnalogIn(ads, ADS.P0)
channel2 = AnalogIn(ads, ADS.P1)

# Main loop to read sensors and capture images if a pest is detected
while True:
    voltage1 = channel1.voltage
    distance1 = get_distance(voltage1)
    voltage2 = channel2.voltage
    distance2 = get_distance(voltage2)

    # Print distances
    print(f"Sensor 1: Voltage: {voltage1:.2f} V, Distance: {distance1:.2f} cm")
    print(f"Sensor 2: Voltage: {voltage2:.2f} V, Distance: {distance2:.2f} cm")

    # Check if any sensor reads less than 10 cm
    if distance1 < 6.5 or distance2 < 6.5:
        print("Pest detected! Triggering camera.")
        time.sleep(2)
        capture_image()
    
    time.sleep(1)  # Delay for 10 second
