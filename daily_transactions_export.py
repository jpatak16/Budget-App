import requests
import os
import time
import datetime
import pandas as pd
from dotenv import load_dotenv

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
start_dt = datetime.datetime(today.year, today.month-1, 1)
start_unix_ts = int(time.mktime(start_dt.timetuple()))

end_dt = datetime.datetime(today.year, today.month+1, 1)
end_unix_ts = int(time.mktime(end_dt.timetuple()))

# Fetch data from SimpleFIN
response = requests.get(url, auth=(username, password), 
                        params={"start-date": start_unix_ts,
                                "end-date": end_unix_ts,
                                "pending": 1}
                        )

# Display error is we fail to feth the accounts
if response.status_code != 200:
    raise Exception(f"Failed to fetch accounts: {response.status_code} - {response.text}")

data = response.json()

# Helper function to convert timestamps into datetime
def ts_to_datetime(ts):
    return datetime.datetime.fromtimestamp(ts)

transactions = []

# Account name and balance for all accounts
for account in data["accounts"]:
    acct_name = account["name"]
    balance_date = ts_to_datetime(account["balance-date"])

    # Info about each transaction within each account
    for trans in account.get("transactions", []):
        transactions.append({
            "account": acct_name,
            "date": ts_to_datetime(trans["posted"]).date(),
            "description": trans["description"],
            "amount": trans["amount"],
            "category": trans.get("category", None)
        })

# Export to csv
df = pd.DataFrame(transactions)

filename = f"data/all_trans/all_transactions_{today.strftime('%Y-%m-%d')}.csv"
df.to_csv(filename, index=False)

# Confirmation message
print(f" Successfully exported {len(df)} transactions to {filename}")