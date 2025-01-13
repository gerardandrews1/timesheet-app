import streamlit as st
import pandas as pd
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Set page config
st.set_page_config(page_title="Time Clock", layout="wide")

# List of staff members
STAFF_MEMBERS = [
    "Jye",
    "Harry",
    "Colm",
    "Rose",
    # Add all staff names here
]

# Setup Google Sheets credentials
@st.cache_resource
def get_google_sheets_credentials():
    credentials = service_account.Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=['https://www.googleapis.com/auth/spreadsheets']
    )
    return credentials

def get_google_sheet_data(staff_name):
    credentials = get_google_sheets_credentials()
    service = build('sheets', 'v4', credentials=credentials)
    sheet = service.spreadsheets()
    
    SPREADSHEET_ID = st.secrets["general"]["spreadsheet_id"]
    RANGE_NAME = f"'{staff_name}'!A:E"  # Each staff member has their own tab
    
    try:
        result = sheet.values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=RANGE_NAME
        ).execute()
        
        values = result.get('values', [])
        if not values:
            return pd.DataFrame(columns=['Date', 'Start Time', 'Alcohol Check', 'End Time'])
        
        return pd.DataFrame(values[1:], columns=values[0])
    except Exception as e:
        st.error(f"Error loading data for {staff_name}. Make sure their sheet exists.")
        return pd.DataFrame(columns=['Date', 'Start Time', 'Alcohol Check', 'End Time'])

def append_to_sheet(staff_name, row_data):
    credentials = get_google_sheets_credentials()
    service = build('sheets', 'v4', credentials=credentials)
    sheet = service.spreadsheets()
    
    SPREADSHEET_ID = st.secrets["spreadsheet_id"]
    RANGE_NAME = f"'{staff_name}'!A:E"
    
    values = [row_data]
    body = {'values': values}
    
    result = sheet.values().append(
        spreadsheetId=SPREADSHEET_ID,
        range=RANGE_NAME,
        valueInputOption='USER_ENTERED',
        body=body
    ).execute()

# Sidebar for staff selection
with st.sidebar:
    st.title("Staff Selection")
    selected_staff = st.selectbox(
        "Select Staff Member",
        options=STAFF_MEMBERS,
        index=0
    )

# Main app
st.title('Time Clock')

# Show selected staff member
st.subheader(f"Logged in as: {selected_staff}")

# Create two columns for Start and End buttons
col1, col2 = st.columns(2)

with col1:
    if st.button('Start Work', use_container_width=True):
        now = datetime.now()
        row_data = [
            now.strftime('%Y/%m/%d'),
            now.strftime('%I:%M:%S %p'),
            '0.00mg',
            ''
        ]
        append_to_sheet(selected_staff, row_data)
        st.success(f'Clocked in at {row_data[1]}')

with col2:
    if st.button('End Work', use_container_width=True):
        df = get_google_sheet_data(selected_staff)
        # Find the last row without an end time
        if not df.empty and any(df['End Time'].isna() | (df['End Time'] == '')):
            now = datetime.now()
            end_time = now.strftime('%I:%M:%S %p')
            # Update the last row with end time
            row_number = df[df['End Time'].isna() | (df['End Time'] == '')].index[-1] + 2
            
            SPREADSHEET_ID = st.secrets["spreadsheet_id"]
            RANGE_NAME = f"'{selected_staff}'!D{row_number}"
            
            credentials = get_google_sheets_credentials()
            service = build('sheets', 'v4', credentials=credentials)
            sheet = service.spreadsheets()
            
            body = {'values': [[end_time]]}
            result = sheet.values().update(
                spreadsheetId=SPREADSHEET_ID,
                range=RANGE_NAME,
                valueInputOption='USER_ENTERED',
                body=body
            ).execute()
            
            st.success(f'Clocked out at {end_time}')
        else:
            st.warning('No open clock-in entry found')

# Display timesheet
st.markdown('### Recent Time Entries')
df = get_google_sheet_data(selected_staff)
if not df.empty:
    st.dataframe(
        df.sort_values('Date', ascending=False),
        hide_index=True,
        use_container_width=True
    )