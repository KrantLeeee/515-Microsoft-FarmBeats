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
import RPi.GPIO as GPIO
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s:%(message)s')

# Suppress detailed logs from azure
azure_logger = logging.getLogger('azure.core.pipeline.policies.http_logging_policy')
azure_logger.setLevel(logging.WARNING)

# Load environment variables
load_dotenv()

# Initialize Azure Blob Storage and Table Storage clients
# Please prepare your connection string to Azure Storage Account
connect_str = os.getenv("connection_string")
blob_service_client = BlobServiceClient.from_connection_string(connect_str)
asset_container_name = 'assets'
device_container_name = 'devicetest01' # Change the container name into yours
asset_container_client = blob_service_client.get_container_client(asset_container_name)
device_container_client = blob_service_client.get_container_client(device_container_name)

# Azure Table Storage setup
table_service = TableServiceClient.from_connection_string(connect_str)
table_name = 'DeviceTest01' # Change the table name into yours
table_client = table_service.get_table_client(table_name)

# Ensure the table exists, create if not
try:
    table_client.create_table()
except Exception as e:
    logging.info("Table already exists or another error occurred:", e)

# Setup GPIO for LED control
LED_PIN = 17  # GPIO pin to which the LED strip is connected
GPIO.setmode(GPIO.BCM)
GPIO.setup(LED_PIN, GPIO.OUT)

# Function to check for the trigger file
def check_for_trigger_file():
    try:
        blob_list = asset_container_client.list_blobs(name_starts_with="trigger.txt")
        for blob in blob_list:
            logging.info("Trigger file found.")
            return True
    except Exception as e:
        logging.error(f"Error checking for trigger file: {e}")
    return False

# Function to delete the trigger file
def delete_trigger_file():
    try:
        asset_container_client.delete_blob("trigger.txt")
        logging.info("Trigger file deleted.")
    except Exception as e:
        logging.error(f"Error deleting trigger file: {e}")

# Function to upload a file to Azure Blob Storage and store metadata in Azure Table Storage
def upload_file_and_save_metadata(file_path, description, weevil_count):
    try:
        blob_client = blob_service_client.get_blob_client(container=device_container_name, blob=os.path.basename(file_path))

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

        logging.info(f"File uploaded and metadata saved: {file_path}")
        return blob_url, metadata
    except Exception as e:
        logging.error(f"Error uploading file and saving metadata: {e}")
        return None, None

# Function to capture images using Raspberry Pi's camera
def capture_image(previous_image=None):
    save_path = os.getenv("save_path")
    os.makedirs(save_path, exist_ok=True)
    
    filename = os.path.join(save_path, time.strftime("%Y%m%d-%H%M%S") + ".jpg")
    command = f"libcamera-still -o '{filename}' --autofocus-mode auto --tuning-file /usr/share/libcamera/ipa/rpi/vc4/imx477_af.json"
    
    try:
        # Turn on the LED before capturing the image
        GPIO.output(LED_PIN, GPIO.HIGH)
        logging.info("LED on")
        
        # Wait for 2 seconds
        time.sleep(2)
        
        logging.info(f"Executing command: {command}")
        os.system(command)
        
        # Turn off the LED after capturing the image
        GPIO.output(LED_PIN, GPIO.LOW)
        logging.info("LED off")
        
        if os.path.exists(filename) and os.path.isfile(filename):
            logging.info(f"Captured {filename}")
            current_image = cv2.imread(filename)
            if current_image is not None:
                if previous_image is not None:
                    similarity, diff = compare_images(previous_image, current_image)
                    if similarity > 0.97:
                        count = count_new_weevils(diff)
                        description = f"Time: {time.strftime('%H:%M:%S')}\nPest category: Weevil\nNew weevils found: {count}"
                    else:
                        count = process_image(current_image)
                        description = f"Time: {time.strftime('%H:%M:%S')}\nPest category: Weevil\nNumber: {count}"
                else:
                    count = process_image(current_image)
                    description = f"Time: {time.strftime('%H:%M:%S')}\nPest category: Weevil\nNumber: {count}"
                    
                upload_file_and_save_metadata(filename, description, count)
                logging.info(f"Processed and uploaded {filename}: {count} weevils found")
            else:
                logging.error(f"Failed to load image {filename}")
        else:
            logging.error(f"Image file {filename} does not exist or is not a file")

        return current_image
    except Exception as e:
        logging.error(f"Error capturing image: {e}")
        return previous_image

# Function to compare images
def compare_images(imageA, imageB):
    grayA = cv2.cvtColor(imageA, cv2.COLOR_BGR2GRAY)
    grayB = cv2.cvtColor(imageB, cv2.COLOR_BGR2GRAY)
    diff = cv2.absdiff(grayA, grayB)
    _, diff = cv2.threshold(diff, 60, 255, cv2.THRESH_BINARY)
    similarity = 1 - (cv2.countNonZero(diff) / diff.size)
    return similarity, diff

# Function to count new weevils based on image differencing
def count_new_weevils(diff_image):
    contours, _ = cv2.findContours(diff_image, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    min_area = 27785  # Minimum area to be considered a weevil
    max_area = 266000  # Maximum area to be considered a weevil
    new_weevil_count = 0

    for contour in contours:
        area = cv2.contourArea(contour)
        if min_area < area < max_area:
            new_weevil_count += 1

    return new_weevil_count

def crop_center_square(image):
    # Get image dimensions
    height, width = image.shape[:2]
    
    # Coordinates for cropping (these should be adjusted based on your specific image)
    top = 150  # Adjust as needed
    bottom = height - 400  # Adjust as needed
    left = 100  # Adjust as needed
    right = width - 100  # Adjust as needed
    
    # Print dimensions for debugging
    print(f"Image dimensions: height={height}, width={width}")
    print(f"Cropping to: top={top}, bottom={bottom}, left={left}, right={right}")
    
    # Crop the image to the desired region
    cropped_img = image[top:bottom, left:right]
    
    return cropped_img


# Function to process an image and count the weevils
def process_image(image):
    cropped_image = crop_center_square(image)
    gray = cv2.cvtColor(cropped_image, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 60, 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    min_area = 27785  # Minimum area to be considered a weevil
    max_area = 266000  # Maximum area to be considered a weevil
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
previous_image = None
while True:
    voltage1 = channel1.voltage
    distance1 = get_distance(voltage1)
    voltage2 = channel2.voltage
    distance2 = get_distance(voltage2)

    # Print distances
    logging.info(f"Sensor 1: Voltage: {voltage1:.2f} V, Distance: {distance1:.2f} cm")
    logging.info(f"Sensor 2: Voltage: {voltage2:.2f} V, Distance: {distance2:.2f} cm")

    # Check if trigger file exists
    if check_for_trigger_file():
        logging.info("Trigger file detected! Capturing image.")
        previous_image = capture_image(previous_image)
        delete_trigger_file()
    elif distance1 < 9.5 or distance2 < 9.5:
        logging.info("Pest detected! Triggering camera.")
        previous_image = capture_image(previous_image)
    
    time.sleep(5)  # Delay for 5 seconds. You can change the number to change the detection frequency

# Cleanup GPIO settings before exiting
GPIO.cleanup()

