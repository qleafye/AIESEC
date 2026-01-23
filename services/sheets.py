import gspread
from config import config
import logging

async def append_to_sheet(data: list):
    """
    Appends a row of data to the configured Google Sheet.
    This function runs synchronously because gspread is sync, 
    so we should be careful or run it in an executor if high load.
    For this bot, direct call is acceptable or we can wrap in to_thread.
    """
    if not config.GOOGLE_SHEET_ID or not config.GOOGLE_CREDENTIALS_FILE:
        logging.warning("Google Sheet ID or Credentials not set. Skipping sheet export.")
        return

    try:
        # Authenticate using the credentials file directly with gspread
        gc = gspread.service_account(filename=config.GOOGLE_CREDENTIALS_FILE)
        
        # Open the sheet
        sh = gc.open_by_key(config.GOOGLE_SHEET_ID)
        sheet = sh.sheet1
        
        # Append the row
        sheet.append_row(data)
        logging.info(f"Successfully appended to Google Sheet: {data}")
        
    except Exception as e:
        logging.error(f"Failed to append to Google Sheet: {e}")
