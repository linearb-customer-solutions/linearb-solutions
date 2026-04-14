import requests
import csv
from datetime import datetime

API_URL = "https://public-api.linearb.io/api/"
API_KEY = "5273a1d13f91d6ccbd137cd47d6990b8"

HEADERS = {
    "x-api-key": API_KEY
}


# -----------------------------
# USER INPUT 
# -----------------------------
START_DATE = "2025-03-01"  # YYYY-MM-DD
END_DATE = "2025-03-31"    # YYYY-MM-DD
OUTPUT_FILE = "linearb_code_changes.csv"
# -----------------------------


def fetch_team_ids():
    """
    Pull all team IDs from LinearB
    """

    response = requests.get(API_URL + 'v2/teams', headers=HEADERS)

    if response.status_code != 200:
        raise Exception(f"Failed to fetch teams: {response.text}")

    data = response.json()

    teams = data["items"]

    print(f"Found {len(teams)} teams:")
    for t in teams:
        print(f" - {t['name']}")

    return [t["id"] for t in teams]

def fetch_contributors():
    """
    Pull all contributor IDs and names/emails from LinearB, handling pagination
    """
    contributors = {}
    offset = 0
    limit = 50  # API returns a max of 50 items per call

    while True:
        response = requests.get(
            API_URL + 'v1/users',
            headers=HEADERS,
            params={"offset": offset, "limit": limit}
        )

        if response.status_code != 200:
            raise Exception(f"Failed to fetch contributors: {response.text}")

        data = response.json()

        for c in data["items"]:
            for cu in c['connected_users']['contributors']:
                if cu['sensor_type_id'] == 1:
                    contributors[int(cu['contributor_id'])] = {"name": c["name"], "email": c["email"]}

        print(f"Fetched {len(data['items'])} contributors (offset: {offset})")

        # Check if we have fetched all contributors
        if len(data["items"]) < limit:
            break

        offset += limit

    print(f"Total contributors fetched: {len(contributors)}")

    return contributors


def build_metrics_query(start_iso, end_iso, team_ids):

    return {
        "group_by": "contributor",
        "roll_up": "custom",
        "requested_metrics": [
            {
            "name": "commit.total_changes"
            },
            {
            "name": "commit.activity.new_work.count"
            }
        ],
        "time_ranges": [
            {
            "after": start_iso,
            "before": end_iso
            }
        ],
        "team_ids": team_ids
    }
    


def fetch_metrics(start_iso, end_iso, team_ids):
    payload = build_metrics_query(start_iso, end_iso, team_ids)

    response = requests.post(API_URL + 'v2/measurements', json=payload, headers=HEADERS)

    if response.status_code != 200:
        raise Exception(f"Query failed: {response.text}")

    data = response.json()

    return data[0]["metrics"]


def write_csv(results, contributors, output_file):
    with open(output_file, "w", newline="") as csvfile:
        fieldnames = ["name", "email", "total_changes"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        writer.writeheader()

        for r in results:
            try:
                c = contributors[r['contributor_id']]
            except KeyError:
                print("Missed contributor ID: ", r['contributor_id'])
                continue

            total_changes = 0
            total_changes = r["commit.total_changes"]

            writer.writerow({
                "name": c["name"],
                "email": c["email"],
                "total_changes": total_changes
            })

if __name__ == "__main__":
    print(f"Fetching data from {START_DATE} to {END_DATE}...")

    team_ids = fetch_team_ids()
    contributors = fetch_contributors()
    results = fetch_metrics(START_DATE, END_DATE, team_ids)

    write_csv(results, contributors, OUTPUT_FILE)
    print(f"CSV written to {OUTPUT_FILE}")