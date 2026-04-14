import requests
import csv
import argparse
API_URL = "https://public-api.linearb.io/api/"


def fetch_team_ids(HEADERS):
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

def fetch_contributors(HEADERS):
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


def build_metrics_query(start_date, end_date, team_ids):

    return {
        "group_by": "contributor",
        "roll_up": "custom",
        "requested_metrics": [
            {
            "name": "commit.total_changes"
            }
        ],
        "time_ranges": [
            {
            "after": start_date,
            "before": end_date
            }
        ],
        "team_ids": team_ids
    }
    


def fetch_metrics(HEADERS, start_date, end_date, team_ids):
    payload = build_metrics_query(start_date, end_date, team_ids)

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
    parser = argparse.ArgumentParser(description="Fetch LinearB metrics and save to CSV.")
    parser.add_argument("--start-date", required=True, help="Start date in YYYY-MM-DD format")
    parser.add_argument("--end-date", required=True, help="End date in YYYY-MM-DD format")
    parser.add_argument("--api-key", required=True, help="LinearB API key")
    parser.add_argument("--output-file", required=True, help="Output CSV file name")

    args = parser.parse_args()

    START_DATE = args.start_date
    END_DATE = args.end_date
    API_KEY = args.api_key
    OUTPUT_FILE = args.output_file

    HEADERS = {
    "x-api-key": API_KEY
    }

    print(f"Fetching data from {START_DATE} to {END_DATE}...")

    team_ids = fetch_team_ids(HEADERS)
    contributors = fetch_contributors(HEADERS)
    results = fetch_metrics(HEADERS, START_DATE, END_DATE, team_ids)

    write_csv(results, contributors, OUTPUT_FILE)
    print(f"CSV written to {OUTPUT_FILE}")
