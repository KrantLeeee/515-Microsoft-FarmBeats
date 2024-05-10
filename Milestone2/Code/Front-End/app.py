import streamlit as st
import os
import matplotlib.pyplot as plt
from azure.data.tables import TableServiceClient
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize TableServiceClient
connect_str = os.getenv("connection_string")
table_service = TableServiceClient.from_connection_string(connect_str)
table_client = table_service.get_table_client("DeviceTest01")

# Function to get data by date using the "TS" field
def get_data_by_date_range(start_date, end_date):
    query = f"TS ge '{start_date.isoformat()}Z' and TS lt '{end_date.isoformat()}Z'"
    data = table_client.query_entities(query, select=['ImageUrl', 'Description', 'TS', 'Weevil_number'])
    return sorted(data, key=lambda x: x['TS'])

# Function to aggregate data monthly or daily
def aggregate_data(data, by='month'):
    aggregated = {}
    for entry in data:
        timestamp = datetime.fromisoformat(entry['TS'].replace('Z', ''))
        if by == 'month':
            key = timestamp.strftime('%Y-%m')
        else:
            key = timestamp.strftime('%Y-%m-%d')
        aggregated[key] = aggregated.get(key, 0) + entry.get('Weevil_number', 0)
    return aggregated

# Function to generate a line chart for peaweevil detection
def generate_peaweevil_chart(data, by='month'):
    aggregated = aggregate_data(data, by)
    timeline = list(aggregated.keys())
    counts = list(aggregated.values())

    plt.figure(figsize=(10, 6))
    plt.plot(timeline, counts, marker='o', linestyle='-')
    plt.xlabel('Timeline')
    plt.ylabel('Peaweevil Number')
    plt.title(f'Peaweevil Detection Chart ({by.capitalize()})')
    plt.xticks(rotation=45)
    plt.grid(True)
    st.pyplot(plt)

# SVG icons
user_icon_svg = """
<svg width="39" height="39" viewBox="0 0 39 39" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M0.804688 0.444336H38.2352V37.8749H0.804688V0.444336Z" fill="white" fill-opacity="0.01"/>
<path d="M19.5197 16.0402C22.9651 16.0402 25.7581 13.2472 25.7581 9.80178C25.7581 6.35639 22.9651 3.56335 19.5197 3.56335C16.0743 3.56335 13.2812 6.35639 13.2812 9.80178C13.2812 13.2472 16.0743 16.0402 19.5197 16.0402Z" stroke="black" stroke-width="7.10427" stroke-linecap="round" stroke-linejoin="round"/>
<path d="M33.5573 34.7556C33.5573 27.0035 27.2729 20.7191 19.5208 20.7191C11.7687 20.7191 5.48438 27.0035 5.48438 34.7556" stroke="black" stroke-width="7.10427" stroke-linecap="round" stroke-linejoin="round"/>
</svg>
"""

notification_icon_svg = """
<svg width="44" height="44" viewBox="0 0 44 44" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M0 0H43.375V43.375H0V0Z" fill="white" fill-opacity="0.01"/>
<path d="M39.7591 14.4583V32.5312H26.2044L21.6862 37.0495L17.168 32.5312H3.61328V5.42188H30.7227" stroke="black" stroke-width="1.7975" stroke-linecap="round" stroke-linejoin="round"/>
<path d="M20.7812 18.0729H22.5908" stroke="black" stroke-width="1.7975" stroke-linecap="round"/>
<path d="M29.8203 18.0729H31.6266" stroke="black" stroke-width="1.7975" stroke-linecap="round"/>
<path d="M11.7461 18.0729H13.5524" stroke="black" stroke-width="1.7975" stroke-linecap="round"/>
<path d="M38.8555 9.03662C40.3527 9.03662 41.5664 7.82289 41.5664 6.32568C41.5664 4.82847 40.3527 3.61475 38.8555 3.61475C37.3583 3.61475 36.1445 4.82847 36.1445 6.32568C36.1445 7.82289 37.3583 9.03662 38.8555 9.03662Z" fill="black"/>
</svg>
"""

# Streamlit App Layout
# Top Bar
col1, col2, col3 = st.columns([1, 5, 1])
with col1:
    st.image('https://515farmdetector.blob.core.windows.net/assets/Logo.png', width=80)
with col2:
    st.write("<h1 style='text-align:center;'>FarmDetector</h1>", unsafe_allow_html=True)
with col3:
    st.write(notification_icon_svg, unsafe_allow_html=True)

# Page Split Layout
main_col, sub_col = st.columns([2, 1])

# Main Column (Left)
with main_col:
    # Peaweevil Detection Chart
    st.write("### Peaweevil Detection Chart")
    chart_type = st.radio("Select view mode", ("Month", "Day"))
    by = 'month' if chart_type == "Month" else 'day'
    today = datetime.today()
    start_date = today.replace(day=1) if by == 'month' else today - timedelta(days=7)
    data = get_data_by_date_range(start_date, today)
    generate_peaweevil_chart(data, by)

    # Date Picker
    st.write("### Choose a date")
    selected_date = st.date_input("Select a date", today)

    # Display Images and Descriptions for the selected date
    date_data = get_data_by_date_range(datetime(selected_date.year, selected_date.month, selected_date.day), 
                                       datetime(selected_date.year, selected_date.month, selected_date.day) + timedelta(days=1))
    if date_data:
        for entry in date_data:
            st.image(entry['ImageUrl'], caption=entry['Description'])
    else:
        st.write("No data found for the selected date.")

    # Warning List
    st.write("### Warning List")
    warnings = [{'title': 'Weevil count high', 'severity': 'High'}, {'title': 'Device disconnected', 'severity': 'Medium'}]
    for warning in warnings:
        severity_color = 'red' if warning['severity'] == 'High' else 'orange'
        st.write(f"<span style='color:{severity_color};'>●</span> {warning['title']}", unsafe_allow_html=True)
        st.checkbox(f"Mark as solved: {warning['title']}")

    # Expert Suggestion Area
    st.write("### Expert Suggestions")
    st.write("Call us for further assistance or visit our knowledge base.")

# Sub Column (Right)
with sub_col:
    # My Device List
    st.write("### My Device List")
    st.write("Device 1 (Update 2h ago) ⯈")
    st.write("Device 2 (Update 2h ago) ⯈")
    st.write("+ Add new device")

    # My Profile
    st.write("### My Profile")
    st.write("Contact Information:")
    st.write("Email: youremail@example.com")
    st.write("Phone: +123456789")
    st.write("Device Settings: Device 1, Device 2")
