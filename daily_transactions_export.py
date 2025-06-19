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
                                "end-date": end_unix_ts}
                        )

# Display error is we fail to feth the accounts
if response.status_code != 200:
    raise Exception(f"Failed to fetch accounts: {response.status_code} - {response.text}")

data = response.json()

# Helper function to convert timestamps into datetime
def ts_to_datetime(ts):
    return datetime.datetime.fromtimestamp(ts)

account_overview = []
transactions = []

# Account name and balance for all accounts
for account in data["accounts"]:
    acct_name = account["name"]
    account_overview.append({
        "acct_name": account["name"],
        "date_updated": ts_to_datetime(account["balance-date"]),
        "balance": account["balance"],
        "date_run": datetime.datetime(today.year, today.month, today.day)
    })
    

    # Info about each transaction within each account
    for trans in account.get("transactions", []):
        transactions.append({
            "account": acct_name,
            "id": trans["id"],
            "description": trans["description"],
            "amount": trans["amount"],
            "payee": trans["payee"],
            "transacted_at": ts_to_datetime(trans["transacted_at"]).date()
        })

# Turn our pulled data into pandas dfs
acct_df = pd.DataFrame(account_overview)
trans_df = pd.DataFrame(transactions)

# Import prior data
acct_filename = f"data/account_balances.csv"
trans_log_filename = f"data/trans_log.xlsx"

old_trans_log_df = pd.read_excel(trans_log_filename)

# Find rows from our new trans file that are not already in the transaction log
new_transactions = trans_df[~trans_df['id'].isin(old_trans_log_df['id'])]

# Merge old trans log and new transactions and sort by date
if len(new_transactions)>0:
    new_trans_log_df = pd.concat([old_trans_log_df, new_transactions])
    new_trans_log_df['transacted_at'] = pd.to_datetime(new_trans_log_df['transacted_at'])
    new_trans_log_df = new_trans_log_df.sort_values("transacted_at")

if len(new_transactions)==0:
    new_trans_log_df = old_trans_log_df

# Save
acct_file_exists = os.path.isfile(acct_filename)
trans_log_exists = os.path.isfile(trans_log_filename)

#acct_df.to_csv(acct_filename, mode='a', index=False, header=not acct_file_exists)
new_trans_log_df.to_excel(trans_log_filename, index=False)

# Confirmation message
print(f" Successfully exported account balances for {len(acct_df)} accounts to {acct_filename}")
print(f" Successfully exported {len(new_transactions)} new transactions to {trans_log_filename}")