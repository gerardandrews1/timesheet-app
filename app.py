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
    RANGE_NAME = f"'{staff_name}'!A:E"  # Include Hours Worked column
    
    try:
        result = sheet.values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=RANGE_NAME
        ).execute()
        
        values = result.get('values', [])
        if not values:
            return pd.DataFrame(columns=['Date', 'Start Time', 'Alcohol Check', 'End Time', 'Hours Worked'])
        
        # Ensure all rows have 5 columns by padding with empty strings if necessary
        padded_values = [row + [''] * (5 - len(row)) for row in values[1:]]
        
        # Create DataFrame with all 5 columns
        df = pd.DataFrame(padded_values, columns=['Date', 'Start Time', 'Alcohol Check', 'End Time', 'Hours Worked'])
        
        # Calculate hours worked for any rows missing it
        mask = (df['End Time'].notna()) & (df['End Time'] != '') & (df['Hours Worked'].isin(['', None]))
        df.loc[mask, 'Hours Worked'] = df[mask].apply(
            lambda row: calculate_hours_worked(row['Start Time'], row['End Time']), 
            axis=1
        )
        
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
            
            # Get the actual row number in the sheet
            row_number = len(df) + 1  # Add 1 for header row
            
            # Get the start time from the last open row
            last_clock_in_row = open_rows.iloc[-1]
            hours_worked = calculate_hours_worked(last_clock_in_row['Start Time'], end_time)
            
            SPREADSHEET_ID = st.secrets["general"]["spreadsheet_id"]
            
            credentials = get_google_sheets_credentials()
            service = build('sheets', 'v4', credentials=credentials)
            sheet = service.spreadsheets()
            
            update_requests = [
                {
                    "range": f"'{selected_staff}'!D{row_number}:E{row_number}",
                    "values": [[end_time, str(hours_worked)]]  # Update both End Time and Hours Worked
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