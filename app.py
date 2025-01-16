import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import pytz
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Set page config
st.set_page_config(page_title="Time Clock", layout="wide")

# Set timezone to Japan
JST = pytz.timezone('Asia/Tokyo')

# List of staff members
STAFF_MEMBERS = [
    "Jye",
    "Harry",
    "Oisin",
    "Colm",
    "Rose",
    "Joe",
    "Tyler",
    "Jack",
    "Andrew",
    "Kris",
    "Ben",
    "Isaac"
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
    RANGE_NAME = f"'{staff_name}'!A:F"  # Updated to include new column
    
    try:
        result = sheet.values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=RANGE_NAME
        ).execute()
        
        values = result.get('values', [])
        
        # Define the columns we expect
        expected_columns = ['Date', 'Start Time', 'Alcohol Check', 'End Time', 'Hours Worked', 'Early Pick Up']
        
        if not values or len(values) <= 1:  # If no data or only header
            return pd.DataFrame(columns=expected_columns)
            
        # Create DataFrame and handle missing columns
        df = pd.DataFrame(values[1:])  # Skip header row
        
        # If DataFrame is empty after creation, return empty DataFrame with correct columns
        if df.empty:
            return pd.DataFrame(columns=expected_columns)
            
        # Ensure we have enough columns
        while len(df.columns) < len(expected_columns):
            df[len(df.columns)] = ''
            
        # Rename columns
        df.columns = expected_columns
        
        # Fill any missing values with empty string
        df = df.fillna('')
        
        return df
        
    except Exception as e:
        st.error(f"Error loading data for {staff_name}: {str(e)}")
        return pd.DataFrame(columns=expected_columns)

def calculate_hours_worked(start_time, end_time):
    if start_time and end_time:
        try:
            start = datetime.strptime(start_time, '%I:%M:%S %p')
            end = datetime.strptime(end_time, '%I:%M:%S %p')
            hours_worked = (end - start).total_seconds() / 3600
            return round(hours_worked, 2)
        except ValueError:
            return ''
    else:
        return ''

def append_to_sheet(staff_name, row_data):
    credentials = get_google_sheets_credentials()
    service = build('sheets', 'v4', credentials=credentials)
    sheet = service.spreadsheets()
    
    SPREADSHEET_ID = st.secrets["general"]["spreadsheet_id"]
    RANGE_NAME = f"'{staff_name}'!A:F"  # Updated to include new column
    
    # Ensure row_data has all required columns
    while len(row_data) < 6:  # Updated to expect 6 columns
        row_data.append('')
        
    values = [row_data]
    body = {'values': values}
    
    result = sheet.values().append(
        spreadsheetId=SPREADSHEET_ID,
        range=RANGE_NAME,
        valueInputOption='USER_ENTERED',
        body=body
    ).execute()

# Move staff selection to top of page
selected_staff = st.selectbox(
    "Select Staff Member",
    options=STAFF_MEMBERS,
    index=0
)

# Show selected staff member
st.write(f"Logged in as: {selected_staff}")

# Get the current user's last clock-in time
df = get_google_sheet_data(selected_staff)
if not df.empty and any(df['End Time'] == ''):
    last_clock_in = df[df['End Time'] == ''].iloc[-1]['Start Time']
    st.info(f"You last clocked in at {last_clock_in}")

# Create three columns for Start, End, and Early Morning Shift buttons
col1, col2, col3 = st.columns(3)

with col1:
    if st.button('Start Work', use_container_width=True):
        now = datetime.now(JST)
        row_data = [
            now.strftime('%Y/%m/%d'),
            now.strftime('%I:%M:%S %p'),
            '0.00mg',
            '',
            '',
            ''  # Empty Early Pick Up field
        ]
        append_to_sheet(selected_staff, row_data)
        st.success(f'Clocked in at {row_data[1]}')

with col2:
    if st.button('End Work', use_container_width=True):
        df = get_google_sheet_data(selected_staff)
        
        # Find rows without an end time
        open_rows = df[df['End Time'].fillna('') == '']
        
        if not open_rows.empty:
            now = datetime.now(JST)
            end_time = now.strftime('%I:%M:%S %p')
            
            # Get the last row number from the dataframe
            last_row_index = df.index[-1]
            row_number = last_row_index + 2  # Add 2 to account for 0-based index and header row
            
            # Get the start time from the last open row
            start_time = open_rows.iloc[-1]['Start Time']
            hours_worked = calculate_hours_worked(start_time, end_time)
            
            SPREADSHEET_ID = st.secrets["general"]["spreadsheet_id"]
            
            credentials = get_google_sheets_credentials()
            service = build('sheets', 'v4', credentials=credentials)
            sheet = service.spreadsheets()
            
            update_requests = [
                {
                    "range": f"'{selected_staff}'!D{row_number}:E{row_number}",
                    "values": [[end_time, str(hours_worked)]]
                }
            ]
            
            body = {"valueInputOption": "USER_ENTERED", "data": update_requests}
            result = sheet.values().batchUpdate(
                spreadsheetId=SPREADSHEET_ID,
                body=body
            ).execute()
            
            st.success(f'Clocked out at {end_time}')
        else:
            st.warning('No open clock-in entry found')

with col3:
    if st.button('Early Morning Shift', use_container_width=True):
        now = datetime.now(JST)
        # Set fixed times for early morning shift
        start_time = '06:00:00 AM'
        end_time = '08:30:00 AM'
        
        # Calculate hours worked
        hours = calculate_hours_worked(start_time, end_time)
        
        row_data = [
            now.strftime('%Y/%m/%d'),  # Current date
            start_time,
            '0.00mg',
            end_time,
            str(hours),
            'Yes'  # Mark as early pickup
        ]
        append_to_sheet(selected_staff, row_data)
        st.success(f'Added early morning shift: {start_time} - {end_time}')

# Display timesheet
st.markdown('### Recent Time Entries')
df = get_google_sheet_data(selected_staff)
if not df.empty:
    # Convert DataFrame to display format
    display_df = df.copy()
    st.dataframe(
        display_df,
        use_container_width=True,
        height=300,
        hide_index=True  # Hide the index column
    )
else:
    st.info("No time entries found")