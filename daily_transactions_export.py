import requests
import sys
import os
import time
import datetime
import pandas as pd
from dotenv import load_dotenv
import gspread
from oauth2client.service_account import ServiceAccountCredentials

try:
    # Define the scope for Google Sheets
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

    # Authenticate using the service account
    creds = ServiceAccountCredentials.from_json_keyfile_name("budget-app-467122-8956d11132d3.json", scope)
    client = gspread.authorize(creds)

    # Load variables from .env
    load_dotenv()

    # Read from environment
    access_url = os.getenv("SIMPLEFIN_ACCESS_TOKEN")

    # Display error if token not found
    if access_url is None:
        raise ValueError("SimpleFIN Access Token was not found in environment.")

    # Parse authentication from access URL
    scheme, rest = access_url.split("//", 1)
    auth, rest = rest.split("@", 1)

    username, password = auth.split(":", 1)

    url = scheme + "//" + rest + "/accounts"

    today = datetime.datetime.now()

    # Set start and end dates for our API call
    start_dt = datetime.datetime(today.year, today.month - 1, 1)
    start_unix_ts = int(time.mktime(start_dt.timetuple()))

    end_dt = datetime.datetime(today.year, today.month + 1, 1)
    end_unix_ts = int(time.mktime(end_dt.timetuple()))

    # Fetch data from SimpleFIN
    response = requests.get(
        url,
        auth=(username, password),
        params={"start-date": start_unix_ts, "end-date": end_unix_ts},
    )

    # Display error if we fail to fetch the accounts
    if response.status_code != 200:
        raise Exception(f"Failed to fetch accounts: {response.status_code} - {response.text}")

    data = response.json()

    # Manually handle some abnormally/incorrectly behaving accounts
    data["accounts"] = [
        {**a, "name": "Health Savings Account (JP)"} if a["id"] == os.getenv("hsa_jp_act_id")
        else {**a, "name": "Bilt Mastercard"} if a["id"] == os.getenv("bilt_act_id")
        else a
        for a in data["accounts"]
        if a["id"] != os.getenv("baylor_act_id")
    ]

    # Helper function to convert timestamps into datetime
    def ts_to_datetime(ts):
        return datetime.datetime.fromtimestamp(ts)

    account_overview = []
    transactions = []

    # Account name and balance for all accounts
    for account in data["accounts"]:
        acct_name = account["name"]
        account_overview.append(
            {
                "acct_name": account["name"],
                "date_updated": ts_to_datetime(account["balance-date"]),
                "balance": account["balance"],
                "date_run": today.date(),
            }
        )

        # Info about each transaction within each account
        for trans in account.get("transactions", []):
            transactions.append(
                {
                    "account": acct_name,
                    "id": trans["id"],
                    "description": trans["description"],
                    "amount": trans["amount"],
                    "payee": trans["payee"],
                    "transacted_at": ts_to_datetime(trans["transacted_at"]).date(),
                    "category": "",
                    "subcategory": "",
                }
            )

    # Turn our pulled data into pandas dfs
    acct_df = pd.DataFrame(account_overview)
    trans_df = pd.DataFrame(transactions)

    acct_df["date_run"] = pd.to_datetime(acct_df["date_run"]).dt.strftime("%m/%d/%Y")
    acct_df["date_updated"] = pd.to_datetime(acct_df["date_updated"]).dt.strftime("%m/%d/%Y %H:%M")

    # Open Google Sheets
    acct_sheet = client.open("JHP-Account-Balances").sheet1
    trans_sheet = client.open("JHP-Transaction-Log").sheet1

    # Get all values from the sheet
    old_trans_data = trans_sheet.get_all_values()

    # Convert to DataFrame
    old_trans_log_df = pd.DataFrame(old_trans_data[1:], columns=old_trans_data[0])

    # Find rows from our new trans file that are not already in the transaction log
    new_transactions = trans_df[~trans_df["id"].isin(old_trans_log_df["id"])]

    if len(new_transactions) > 0:
        # Prepare only new rows for appending
        new_rows = new_transactions.astype(str).values.tolist()

        # Append new rows to Google Sheet
        trans_sheet.append_rows(new_rows, value_input_option="USER_ENTERED")

    new_acct_rows = acct_df.astype(str).values.tolist()
    acct_sheet.append_rows(new_acct_rows, value_input_option="USER_ENTERED")

    # Confirmation message
    print(f" Successfully exported account balances for {len(acct_df)} accounts to JHP-Account-Balances")
    print(f" Successfully exported {len(new_transactions)} new transactions to JHP-Transaction-Log")
    print(data.get("errors"))

except Exception as e:
    print(f"Script failed with error: {e}")
    sys.exit(1)
