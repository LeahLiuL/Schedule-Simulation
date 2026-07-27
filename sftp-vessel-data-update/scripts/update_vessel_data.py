#!/usr/bin/env python3
"""
SFTP Vessel Data Update Script
Downloads Vessel Departure Report from SFTP, converts to CSV, pushes to GitHub.

Usage:
  python update_vessel_data.py --work-dir /path/to/repo [options]

All SFTP credentials can be passed via arguments or environment variables.
"""
import paramiko
import pandas as pd
import os
import sys
import csv
import argparse
import subprocess

# Vessel (vessel_voyage) prefixes to exclude from the published CSV.
# "TBN" covers placeholder / to-be-nominated vessels (TBN1, TBN2, ...).
EXCLUDED_VESSEL_PREFIXES = ['TBN']

def parse_args():
    p = argparse.ArgumentParser(description='Download Vessel Departure data from SFTP and convert to CSV')
    p.add_argument('--work-dir', default=os.getcwd(), help='Working directory (git repo root)')
    p.add_argument('--sftp-host', default=os.environ.get('SFTP_HOST', '10.5.4.2'), help='SFTP host')
    p.add_argument('--sftp-port', type=int, default=int(os.environ.get('SFTP_PORT', '6622')), help='SFTP port')
    p.add_argument('--sftp-user', default=os.environ.get('SFTP_USER', 'leah'), help='SFTP username')
    p.add_argument('--sftp-pass', default=os.environ.get('SFTP_PASS', 'Fine@B!'), help='SFTP password')
    p.add_argument('--remote-dir', default=os.environ.get('SFTP_REMOTE_DIR', 'Master Data - Leah'), help='SFTP remote directory')
    p.add_argument('--remote-file', default=os.environ.get('SFTP_REMOTE_FILE', 'Vessel Departure Report.xlsx'), help='SFTP remote filename')
    p.add_argument('--csv-output', default=None, help='CSV output path (default: <work-dir>/shipping_data/bi_vessel_departure.csv)')
    p.add_argument('--no-push', action='store_true', help='Skip git push to GitHub')
    return p.parse_args()


def download_sftp(host, port, user, password, remote_path, local_path):
    print(f"[SFTP] Connecting to {host}:{port}...")
    transport = paramiko.Transport((host, port))
    transport.connect(username=user, password=password)
    sftp = paramiko.SFTPClient.from_transport(transport)
    print("[SFTP] Connected!")

    print(f"[SFTP] Downloading '{remote_path}' -> '{local_path}'")
    sftp.get(remote_path, local_path)
    print(f"[SFTP] Downloaded: {os.path.getsize(local_path)} bytes")

    sftp.close()
    transport.close()
    print("[SFTP] Connection closed.")


def convert_to_csv(xlsx_path, csv_path):
    print(f"[Excel] Reading '{xlsx_path}'...")
    df = pd.read_excel(xlsx_path, engine='openpyxl')
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
        'RESTOWS': 'restows',
        'Arrival Fuel Oil': 'arr_fuel_oil',
        'Arrival LSFO': 'arr_lsfo',
        'Arrival DIESEL OIL': 'arr_diesel_oil',
        'Arrival LSDO': 'arr_lsdo',
        'Departure Fuel Oil': 'dep_fuel_oil',
        'Departure LSFO': 'dep_lsfo',
        'Departure DIESEL OIL': 'dep_diesel_oil',
        'Departure LSDO': 'dep_lsdo',
    }

    df.rename(columns=col_map, inplace=True)
    df.insert(0, 'srl_no', range(1, len(df) + 1))

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

    expected_cols = ['srl_no', 'terminal', 'svc', 'vessel_voyage', 'operator',
                     'arrived_anchorage', 'berth', 'departure', 'wait_time', 'port_stay',
                     'total_moves', 'discharge_full_20gp', 'discharge_empty_20gp',
                     'discharge_full_40hc', 'discharge_empty_40hc',
                     'load_full_20gp', 'load_empty_20gp', 'load_full_40hc', 'load_empty_40hc',
                     'restows', 'total_teu', 'vessel_mpgh',
                     'arr_fuel_oil', 'arr_lsfo', 'arr_diesel_oil', 'arr_lsdo',
                     'dep_fuel_oil', 'dep_lsfo', 'dep_diesel_oil', 'dep_lsdo']

    for col in expected_cols:
        if col not in df.columns:
            df[col] = None

    df = df[expected_cols]

    # Exclude placeholder / to-be-nominated vessels (e.g. TBN1, TBN2 ...) from the
    # published CSV so they never reach GitHub Pages. Case-insensitive prefix match.
    if 'vessel_voyage' in df.columns:
        tail = df['vessel_voyage'].astype(str).str.upper()
        mask = tail.str.startswith(tuple(p.upper() for p in EXCLUDED_VESSEL_PREFIXES))
        removed = int(mask.sum())
        if removed:
            df = df[~mask].copy()
            print(f"[CSV] Removed {removed} rows with excluded vessel prefixes {EXCLUDED_VESSEL_PREFIXES}")

    # Re-number srl_no so it stays sequential after the exclusion above.
    df['srl_no'] = range(1, len(df) + 1)

    for date_col in ['arrived_anchorage', 'berth', 'departure']:
        if date_col in df.columns:
            df[date_col] = pd.to_datetime(df[date_col], errors='coerce').dt.strftime('%Y-%m-%dT%H:%M')

    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    df.to_csv(csv_path, index=False, quoting=csv.QUOTE_MINIMAL)
    print(f"[CSV] Written: {csv_path} ({os.path.getsize(csv_path)} bytes)")
    print(f"[CSV] Total rows: {len(df)}")


def push_to_github(work_dir):
    print("[Git] Adding files...")
    subprocess.run(['git', 'add', '-A'], cwd=work_dir, timeout=30)
    print("[Git] Committing...")
    result = subprocess.run(['git', 'commit', '-m', 'Update vessel departure data from SFTP'],
                          cwd=work_dir, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        print("[Git] Commit output:", result.stdout, result.stderr)
        if "nothing to commit" in (result.stdout + result.stderr):
            print("[Git] No changes to commit.")
            return
    print("[Git] Pushing to GitHub (timeout 120s)...")
    result = subprocess.run(['git', 'push', 'origin', 'main'],
                          cwd=work_dir, capture_output=True, text=True, timeout=120)
    print("[Git] Push stdout:", result.stdout)
    if result.returncode != 0:
        print("[Git] Push stderr:", result.stderr)
        print("[Git] Attempting pull + push...")
        subprocess.run(['git', 'pull', '--no-rebase', 'origin', 'main'], cwd=work_dir, timeout=60)
        result = subprocess.run(['git', 'push', 'origin', 'main'],
                              cwd=work_dir, capture_output=True, text=True, timeout=120)
        if result.returncode == 0:
            print("[Git] Push succeeded after pull!")
        else:
            print("[Git] Push failed:", result.stderr)
    print("[Git] Done!")


def main():
    args = parse_args()
    work_dir = os.path.abspath(args.work_dir)
    local_xlsx = os.path.join(work_dir, 'Vessel_Departure_Report.xlsx')
    csv_path = args.csv_output or os.path.join(work_dir, 'shipping_data', 'bi_vessel_departure.csv')
    remote_path = f"./{args.remote_dir}/{args.remote_file}"

    try:
        download_sftp(args.sftp_host, args.sftp_port, args.sftp_user, args.sftp_pass, remote_path, local_xlsx)
        convert_to_csv(local_xlsx, csv_path)
        if not args.no_push:
            push_to_github(work_dir)
        print("\n[OK] Data updated successfully!")
    except Exception as e:
        print(f"\n[ERROR] {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
