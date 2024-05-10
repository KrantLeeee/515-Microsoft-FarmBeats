from azure.storage.blob import BlobServiceClient
from azure.data.tables import TableServiceClient
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

# Initialize the BlobServiceClient
connect_str = os.getenv("connection_string")  # Use your storage account connection string
blob_service_client = BlobServiceClient.from_connection_string(connect_str)
container_name = 'devicetest01'  # Specify your container name

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
def upload_file_and_save_metadata(file_path, description):
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
        'PartitionKey': 'ImageDescription',  # Use a suitable partition key for your scenario
        'RowKey': os.path.basename(file_path),  # Unique identifier for the row (filename used here)
        'Description': description,
        'ImageUrl': blob_url,
        'FileName': os.path.basename(file_path),  # Storing the file name as well
        'TS': timestamp  # Storing the upload timestamp
    }
    table_client.upsert_entity(entity=metadata)

    return blob_url, metadata

# Example usage
image_path = '/Users/krantlee/Downloads/1714713520862.jpg'
image_description = 'Date: 04/30, 2024\nPest category: Weevil\nNumber: 3\nAdvice: Call us to get more help'
url, metadata = upload_file_and_save_metadata(image_path, image_description)

print("Image URL:", url)
print("Metadata stored:", metadata)