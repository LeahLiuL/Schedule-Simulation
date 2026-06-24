import paramiko
import pandas as pd
import os
import sys
import csv

# SFTP Config
SFTP_HOST = "10.5.4.2"
SFTP_PORT = 6622
SFTP_USER = "leah"
SFTP_PASS = "Fine@B!"
SFTP_REMOTE_DIR = "Master Data - Leah"
SFTP_REMOTE_FILE = "Vessel Departure Report.xlsx"

# Local paths
WORK_DIR = r"C:\Users\leahliu\WorkBuddy\Schedule-Simulation"
LOCAL_XLSX = os.path.join(WORK_DIR, "Vessel_Departure_Report.xlsx")
LOCAL_CSV = os.path.join(WORK_DIR, "shipping_data", "bi_vessel_departure.csv")

def download_sftp():
    print(f"[SFTP] Connecting to {SFTP_HOST}:{SFTP_PORT}...")
    transport = paramiko.Transport((SFTP_HOST, SFTP_PORT))
    transport.connect(username=SFTP_USER, password=SFTP_PASS)
    sftp = paramiko.SFTPClient.from_transport(transport)
    print("[SFTP] Connected!")

    remote_path = f"./{SFTP_REMOTE_DIR}/{SFTP_REMOTE_FILE}"
    print(f"[SFTP] Downloading '{remote_path}' -> '{LOCAL_XLSX}'")
    sftp.get(remote_path, LOCAL_XLSX)
    print(f"[SFTP] Downloaded: {os.path.getsize(LOCAL_XLSX)} bytes")

    sftp.close()
    transport.close()
    print("[SFTP] Connection closed.")

def convert_to_csv():
    print(f"[Excel] Reading '{LOCAL_XLSX}'...")
    df = pd.read_excel(LOCAL_XLSX, engine='openpyxl')
    print(f"[Excel] Loaded {len(df)} rows, columns: {list(df.columns)}")

    col_map = {
        'TERMINAL': 'terminal',
        'SVC': 'svc',
        'OPERATOR': 'operator',
        'VESSEL / VOYAGE': 'vessel_voyage',
        'ARRIVED / ANCHORAGE': 'arrived_anchorage',
        'BERTH': 'berth',
        'DEPARTURE': 'departure',
        'WAIT TIME': 'wait_time',
        'PORT STAY': 'port_stay',
        'TOTAL MOVES': 'total_moves',
        'VESSEL MPGH': 'vessel_mpgh',
        'Discharging Vol. Full 20GP': 'discharge_full_20gp',
        'Discharging Vol. Full 40HC': 'discharge_full_40hc',
        'Discharging Vol. Empty 20GP': 'discharge_empty_20gp',
        'Discharging Vol. Empty 40HC': 'discharge_empty_40hc',
        'Load Vol. Full 20GP': 'load_full_20gp',
        'Load Vol. Full 40HC': 'load_full_40hc',
        'Load Vol. Empty 20GP': 'load_empty_20gp',
        'Load Vol. Empty 40HC': 'load_empty_40hc',
    }

    # Rename columns
    df.rename(columns=col_map, inplace=True)

    # Add SRL No
    df.insert(0, 'srl_no', range(1, len(df) + 1))

    # Calculate total_teu
    df['total_teu'] = (
        df.get('discharge_full_20gp', 0).fillna(0) +
        df.get('discharge_empty_20gp', 0).fillna(0) +
        df.get('load_full_20gp', 0).fillna(0) +
        df.get('load_empty_20gp', 0).fillna(0) +
        (df.get('discharge_full_40hc', 0).fillna(0) +
         df.get('discharge_empty_40hc', 0).fillna(0) +
         df.get('load_full_40hc', 0).fillna(0) +
         df.get('load_empty_40hc', 0).fillna(0)) * 2
    )

    # Ensure all expected columns exist
    expected_cols = ['srl_no', 'terminal', 'svc', 'vessel_voyage', 'operator',
                     'arrived_anchorage', 'berth', 'departure', 'wait_time', 'port_stay',
                     'total_moves', 'discharge_full_20gp', 'discharge_empty_20gp',
                     'discharge_full_40hc', 'discharge_empty_40hc',
                     'load_full_20gp', 'load_empty_20gp', 'load_full_40hc', 'load_empty_40hc',
                     'total_teu', 'vessel_mpgh']

    for col in expected_cols:
        if col not in df.columns:
            df[col] = None

    df = df[expected_cols]

    # Convert date columns to ISO format
    for date_col in ['arrived_anchorage', 'berth', 'departure']:
        if date_col in df.columns:
            df[date_col] = pd.to_datetime(df[date_col], errors='coerce').dt.strftime('%Y-%m-%dT%H:%M')

    # Write CSV
    df.to_csv(LOCAL_CSV, index=False, quoting=csv.QUOTE_MINIMAL)
    print(f"[CSV] Written: {LOCAL_CSV} ({os.path.getsize(LOCAL_CSV)} bytes)")
    print(f"[CSV] Total rows: {len(df)}")

def push_to_github():
    print("[Git] Pushing to GitHub...")
    import subprocess
    subprocess.run(['git', 'add', '-A'], cwd=WORK_DIR)
    subprocess.run(['git', 'commit', '-m', 'Update vessel departure data from SFTP'], cwd=WORK_DIR)
    result = subprocess.run(['git', 'push', 'origin', 'main'], cwd=WORK_DIR, capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print("stderr:", result.stderr)
    print("[Git] Done!")

if __name__ == '__main__':
    try:
        download_sftp()
        convert_to_csv()
        push_to_github()
        print("\n✅ All done! Data updated successfully.")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
