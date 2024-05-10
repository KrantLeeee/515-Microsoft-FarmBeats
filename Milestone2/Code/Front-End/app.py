import streamlit as st
import os
import matplotlib.pyplot as plt
from azure.data.tables import TableServiceClient
from datetime import datetime, timedelta
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 初始化 TableServiceClient
connect_str = os.getenv("connection_string")
table_service = TableServiceClient.from_connection_string(connect_str)
table_client = table_service.get_table_client("DeviceTest01")

# 函数：按日期范围获取数据
def get_data_by_date_range(start_date, end_date):
    query = f"TS ge '{start_date.isoformat()}Z' and TS lt '{end_date.isoformat()}Z'"
    data = table_client.query_entities(query, select=['ImageUrl', 'Description', 'TS', 'Weevil_number'])
    return sorted(data, key=lambda x: x['TS'])

# 函数：按月或日汇总数据
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

# 函数：生成豌豆象检测折线图
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

# 函数：查找数据集中最早的时间
def find_earliest_data():
    all_data = table_client.query_entities(query_filter="", select=['TS', 'Weevil_number'])
    all_dates = [datetime.fromisoformat(entry['TS'].replace('Z', '')) for entry in all_data]

    if all_dates:
        return min(all_dates)
    else:
        return datetime.today() - timedelta(days=365)

# SVG 图标
user_icon_svg = """
<svg width="28" height="28" viewBox="0 0 28 28" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M13.9937 1C6.8175 1 1 6.8175 1 13.9937C1 21.1699 6.8175 26.9875 13.9937 26.9875C21.1699 26.9875 26.9875 21.1699 26.9875 13.9937C26.9875 6.8175 21.1699 1 13.9937 1Z" stroke="black" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
<path d="M3.94922 22.2391C3.94922 22.2391 6.84555 18.5415 13.9921 18.5415C21.1386 18.5415 24.0351 22.2391 24.0351 22.2391" stroke="black" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
<path d="M13.9958 13.994C16.1487 13.994 17.8939 12.2488 17.8939 10.0959C17.8939 7.94301 16.1487 6.19775 13.9958 6.19775C11.8428 6.19775 10.0977 7.94301 10.0977 10.0959C10.0977 12.2488 11.8428 13.994 13.9958 13.994Z" stroke="black" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
</svg>
"""

notification_icon_svg = """
<svg width="27" height="27" viewBox="0 0 27 27" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M7.28125 13.9297H20.6215" stroke="black" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
<path d="M7.28125 8.59326H15.2854" stroke="black" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
<path d="M1.94531 24.988V4.5914C1.94531 3.11787 3.13984 1.92334 4.61337 1.92334H23.2898C24.7633 1.92334 25.9578 3.11787 25.9578 4.5914V17.9317C25.9578 19.4052 24.7633 20.5997 23.2898 20.5997H8.56376C7.75324 20.5997 6.98668 20.9682 6.48035 21.6011L3.37075 25.488C2.89809 26.0789 1.94531 25.7447 1.94531 24.988Z" stroke="black" stroke-width="2"/>
</svg>
"""

# Streamlit App 布局
# 顶部栏
with st.container():
    # 将顶部栏用两个列布局，居中对齐并右对齐 SVG 图标
    col1, col2 = st.columns([10, 2], gap="small")
    with col1:
        # 使用 markdown 让图标居中
        st.markdown("<div style='text-align: center;'>"
                    "<img src='https://515farmdetector.blob.core.windows.net/assets/Logo2.png' width='250'>"
                    "</div>", unsafe_allow_html=True)
    with col2:
        # 使用 markdown，让图标垂直居中并右对齐
        st.markdown(
            f"<div style='text-align: right; vertical-align: middle;'>"
            f"<span style='display: inline-block;'>{user_icon_svg}</span>"
            f"<span style='display: inline-block; margin-left: 20px;'>{notification_icon_svg}</span>"
            "</div>", unsafe_allow_html=True
        )

st.write("\n" * 6)  # 插入 3 行的空白行

# 页面分割布局
main_col, sub_col = st.columns([2, 1], gap="large")

# 主列 (左)
with main_col:
    # 豌豆象检测折线图
    st.write("### Peaweevil Detection Chart")
    chart_type = st.radio("Select view mode", ("Month", "Day"))
    by = 'month' if chart_type == "Month" else 'day'
    start_date = find_earliest_data()
    end_date = datetime.today()
    data = get_data_by_date_range(start_date, end_date)
    generate_peaweevil_chart(data, by)

    # Date Picker
    st.write("### Choose a date")
    selected_date = st.date_input("Select a date", datetime.today())

    # Display Images and Descriptions for the selected date
    date_data = get_data_by_date_range(
        datetime(selected_date.year, selected_date.month, selected_date.day),
        datetime(selected_date.year, selected_date.month, selected_date.day) + timedelta(days=1)
    )

    # Number of columns to display side by side
    num_columns = 2

    # Add custom CSS for rounded corners and gap between images
    st.markdown(
        """
        <style>
        .rounded-img {
            border-radius: 10px;  /* Adjust border radius as needed */
            margin-right: 10px;  /* Adjust gap between images */
        }
        </style>
        """, unsafe_allow_html=True
    )

    # Create columns based on the desired number
    cols = st.columns(num_columns)

    # Add images into the columns in a round-robin manner
    if date_data:
        for i, entry in enumerate(date_data):
            col = cols[i % num_columns]
            # Create a formatted description string
            description = (
            f"Time: {entry['TS'][11:19]}<br>"
            f"Pest category: Weevil<br>"
            f"Number: {entry['Weevil_number']}"
            )


            # Render image with the custom class and description below
            col.markdown(
                f"<img src='{entry['ImageUrl']}' width='100%' class='rounded-img'><p>{description}</p>",
                unsafe_allow_html=True
            )
    else:
        st.write("No data found for the selected date.")

    # 警告列表
    st.write("### Warning List")
    warnings = [{'title': 'Weevil count high', 'severity': 'High'}, {'title': 'Device disconnected', 'severity': 'Medium'}]
    for warning in warnings:
        severity_color = 'red' if warning['severity'] == 'High' else 'orange'
        st.write(f"<span style='color:{severity_color};'>●</span> {warning['title']}", unsafe_allow_html=True)
        st.checkbox(f"Mark as solved: {warning['title']}")

    # 专家建议区域
    st.write("### Expert Suggestions")
    st.write("Call us for further assistance or visit our knowledge base.")

# 添加样式，固定侧栏位置
st.markdown(
    """
    <style>
    .fixed-sub-col {
        position: fixed;
        top: 200px;  /* 可以调整顶端距离，根据实际需要更改 */
        right: 200px;  /* 可以调整右端距离，根据页面布局调整 */
        width: 25%;  /* 根据需要调整侧栏宽度 */
        background-color: white;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0px 4px 8px rgba(0, 0, 0, 0.1);
        z-index: 100;
    }
    </style>
    """, unsafe_allow_html=True
)

# 侧列 (右)
with sub_col:
    st.markdown(
        """
        <div class='fixed-sub-col'>
        <h3>My Device List</h3>
        <p>Device 1 (Update 2h ago) ⯈</p>
        <p>Device 2 (Update 2h ago) ⯈</p>
        <p>+ Add new device</p>
        <h3>My Profile</h3>
        <p>Contact Information:</p>
        <p>Email: youremail@example.com</p>
        <p>Phone: +123456789</p>
        <p>Device Settings: Device 1, Device 2</p>
        </div>
        """, unsafe_allow_html=True
    )
