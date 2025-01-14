import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
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
    RANGE_NAME = f"'{staff_name}'!A:E"
    
    try:
        result = sheet.values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=RANGE_NAME
        ).execute()
        
        values = result.get('values', [])
        if not values:
            return pd.DataFrame(columns=['Date', 'Start Time', 'Alcohol Check', 'End Time', 'Hours Worked'])
        
        # Create the DataFrame, handling varying number of columns
        df = pd.DataFrame(values[1:])
        
        # Ensure we have the expected columns, filling in missing ones with empty strings
        expected_columns = ['Date', 'Start Time', 'Alcohol Check', 'End Time', 'Hours Worked']
        for col in expected_columns:
            if col not in df.columns:
                df[col] = ''
        df = df[expected_columns]
        
        # Calculate hours worked
        df['Hours Worked'] = df.apply(lambda row: calculate_hours_worked(row['Start Time'], row['End Time']), axis=1)
        
        return df
    except Exception as e:
        st.error(f"Error loading data for {staff_name}: {str(e)}")
        return pd.DataFrame(columns=['Date', 'Start Time', 'Alcohol Check', 'End Time', 'Hours Worked'])

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
    RANGE_NAME = f"'{staff_name}'!A:E"
    
    # Ensure row_data has all required columns
    while len(row_data) < 5:  # We expect 5 columns now (Date, Start Time, Alcohol Check, End Time, Hours Worked)
        row_data.append('')
        
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

# Get the current user's last clock-in time
df = get_google_sheet_data(selected_staff)
if not df.empty and any(df['End Time'].isna() | (df['End Time'] == '')):
    last_clock_in = df[df['End Time'].isna() | (df['End Time'] == '')].iloc[-1]['Start Time']
    st.info(f"You last clocked in at {last_clock_in}")

# Create two columns for Start and End buttons
col1, col2 = st.columns(2)

with col1:
    if st.button('Start Work', use_container_width=True):
        now = datetime.now()
        row_data = [
            now.strftime('%Y/%m/%d'),
            now.strftime('%I:%M:%S %p'),
            '0.00mg',
            '',
            ''
        ]
        append_to_sheet(selected_staff, row_data)
        st.success(f'Clocked in at {row_data[1]}')

with col2:
    if st.button('End Work', use_container_width=True):
        df = get_google_sheet_data(selected_staff)
        # Find the last row without an end time
        open_rows = df[df['End Time'].isna() | (df['End Time'] == '')]
        if not open_rows.empty:
            now = datetime.now()
            end_time = now.strftime('%I:%M:%S %p')
            # Update the last row with end time and calculate hours worked
            last_clock_in_row = open_rows.iloc[-1]
            row_number = last_clock_in_row.name + 1  # Use 1-based indexing
            
            SPREADSHEET_ID = st.secrets["general"]["spreadsheet_id"]
            RANGE_NAME = f"'{selected_staff}'!D{row_number},E{row_number}"
            
            credentials = get_google_sheets_credentials()
            service = build('sheets', 'v4', credentials=credentials)
            sheet = service.spreadsheets()
            
            update_requests = [
                {
                    "range": f"'{selected_staff}'!D{row_number}",
                    "values": [[end_time]]
                },
                {
                    "range": f"'{selected_staff}'!E{row_number}",
                    "values": [[calculate_hours_worked(last_clock_in_row['Start Time'], end_time)]]
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

# Display timesheet
st.markdown('### Recent Time Entries')
df = get_google_sheet_data(selected_staff)
if not df.empty:
    st.dataframe(df, use_container_width=True, height=300)