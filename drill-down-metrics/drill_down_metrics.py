"""
Drill Down Metrics Report

This script fetches contributor metrics from the LinearB API,
matching those in the LinearB UI for the specified time period.

Please reference the docs on how to call the API: https://docs.linearb.io/api-overview/
"""

import argparse
import csv
import datetime
import json
import requests
from requests.structures import CaseInsensitiveDict


def pull_metrics(api_key, all_teams_id, after_date, before_date):
    headers = CaseInsensitiveDict()
    headers["accept"] = "application/json"
    headers['x-api-key'] = api_key
    headers["content-type"] = "application/json"

    formatted_after_date = after_date.strftime("%Y-%m-%d")
    formatted_before_date = before_date.strftime("%Y-%m-%d")
    url = 'https://public-api.linearb.io/api/v2/measurements/export?file_format=json'

    data = json.dumps({
        "return_no_data": "false",  # need activity within the last 6 months
        "group_by": "contributor",
        "roll_up": "custom",
        "team_ids": [ all_teams_id ],
        "requested_metrics": [
            # My Work
            {  # PRS Merged
                "name": "pr.merged"

            },
            {  # PR Maturity Ratio P75
                "name": "pr.maturity_ratio"
            },
            {  # Number of Commits.
                "name": "commit.total.count"
            },
            {  # PR Size P75
                "name": "pr.merged.size",
                "agg": "p75"
            },
            {  # PR Size average
                "name": "pr.merged.size",
                "agg": "avg"
            },
            {  # Refactor / Rework
                "name": "commit.activity.refactor.count"
            },
            {
                "name": "commit.activity.rework.count",
            },
            {
                "name": "commit.activity.new_work.count",
            },

            {  # WIP
                "name": "branch.state.active"
            },
            {
                "name": "commit.activity_days"
            },
            # Helping Others (
            {  # Number of Reviews
                "name": "pr.reviews"
            },
            {
                "name": "pr.reviewed"
            },
            {  # Developer Experience
                # PR Pickup Time (minutes)
                "name": "branch.time_to_review",
                "agg": "p75"
            },
            {  # Developer Experience
                # PR Pickup Time (minutes)
                "name": "branch.time_to_review",
                "agg": "avg"
            },
            {  # PR Review Time (minutes)
                "name": "branch.review_time",
                "agg": "p75"
            },
            {  # PR Review Time (minutes)
                "name": "branch.review_time",
                "agg": "avg"
            },
            {  # PR Cycle Time (minutes)
                "name": "branch.computed.cycle_time",
                "agg": "p75"
            },
            {  # PR Cycle Time (minutes)
                "name": "branch.computed.cycle_time",
                "agg": "avg"
            },
            {
                "name": "pr.merged"
            }
        ],
        "time_ranges": [
            {
                "after": formatted_after_date,
                "before": formatted_before_date
            }
        ]
    })
    print(data)
    r = requests.post(url, headers=headers, data=data)
    r = requests.get(r.json()['report_url'])
    return r.json()[0]['metrics']

def fetch_individual_metrics(api_key,
                             after_date,
                             before_date,
                             target_file_path="individual_contributors.csv"):

    url = 'https://public-api.linearb.io/api/v2/teams?nonmerged_members_only=true'
    headers = CaseInsensitiveDict()
    headers["accept"] = "application/json, text/plain, */*"
    headers["accept-language"] = "en-US,en;q=0.9"
    headers['x-api-key'] = api_key
    headers["content-type"] = "application/json"
    r = requests.get(url, headers=headers)

    teams = [team for team in r.json()['items'] if team['name'] != 'All Contributors' and team['name'] != 'All Teams']
    all_teams_id = [team for team in r.json()['items'] if team['name'] == 'All Teams'][0]['id']
    print(teams)
    contributors = {contributor['id']: {"name": contributor['name'], "email": contributor['email'], "provider_id": contributor['provider_id']} for team in teams for contributor in team['contributors']}
    for team in teams:
        for contributor in team['contributors']:
            contributors[contributor['id']]['teams'] = contributors[contributor['id']].get('teams', []) + [team['name']]
            contributors[contributor['id']]['metrics'] = {}

    metrics = pull_metrics(api_key, all_teams_id, after_date, before_date)

    contributors_on_teams = set(k for k, v in contributors.items())
    contributors_in_metrics = set(metric['contributor_id'] for metric in metrics)
    missing_contributors = contributors_on_teams - contributors_in_metrics

    for metric in metrics:
        if contributors.get(metric['contributor_id']) is not None:
            contributors[metric['contributor_id']]['metrics'] = {key: val for key, val in metric.items() if key != 'contributor_id'}


    rows = []
    for k, contributor in contributors.items():
        row = { "LinearB ID": k,
                "Name": contributor['name'],
                "Email": contributor['email'],
                "Provider ID": contributor['provider_id'],
                "Teams": contributor['teams'],
                "Has Metrics In Period": k not in missing_contributors,
                # My work metrics
                "PRs Merged": contributor['metrics'].get('pr.merged', -1),
                "PR Maturity Ratio": -1, #contributor['metrics'].get('pr.maturity_ratio', 0),
                "Number of Commits": contributor['metrics'].get('commit.total.count', -1),
                "PR Size (P75)": contributor['metrics'].get('pr.merged.size:p75', -1),
                "PR Size (Average)": contributor['metrics'].get('pr.merged.size:avg', -1),
                "Refactor": contributor['metrics'].get('commit.activity.refactor.count', -1),
                #"Refactor %": contributor['metrics'].get('branch.refactor.count', 0) / contributor['metrics'].get('commit.total_changes', 1),
                "Rework": contributor['metrics'].get('commit.activity.rework.count', -1),
                #"Rework %": contributor['metrics'].get('branch.rework.count', 0) / contributor['metrics'].get('commit.total_changes', 1),
                "New Work": contributor['metrics'].get('commit.activity.new_work.count', -1),
                #"New Work %": contributor['metrics'].get('branch.new_work.count', 0) / contributor['metrics'].get('commit.total_changes', 1),
                "WIP Branches": contributor['metrics'].get('branch.state.active', -1),
                "Active Days": contributor['metrics'].get('commit.activity_days', -1),
                # Helping Others
                "Number of Reviews": contributor['metrics'].get('pr.reviews', -1),
                "PRs Reviewed": contributor['metrics'].get('pr.reviewed', -1),
                # Developer Experience
                "PR Pickup Time (P75)": contributor['metrics'].get('branch.time_to_review:p75', -1),
                "PR Pickup Time (avg)": contributor['metrics'].get('branch.time_to_review:avg', -1),
                "PR Review Time (P75)": contributor['metrics'].get('branch.review_time:p75', -1),
                "PR Review Time (avg)": contributor['metrics'].get('branch.review_time:avg', -1),
                "PR Cycle Time (P75)": contributor['metrics'].get('branch.computed.cycle_time:p75', -1),
                "PR Cycle Time (avg)": contributor['metrics'].get('branch.computed.cycle_time:avg', -1)
          }
        rows.append(row)
    with open(target_file_path, "w") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Create an individual contributor metrics report between the before and after dates for all contributors in the LinearB account on teams.')
    parser.add_argument('apikey', type=str, help='LinearB API key')
    parser.add_argument('start_date', type=str, help='After date (YYYY-MM-DD)')
    parser.add_argument('end_date', type=str, help='Before date (YYYY-MM-DD)')
    parser.add_argument('filepath', type=str, help='File to write the report csv to.')

    args = parser.parse_args()

    try:
        after_date = datetime.datetime.strptime(args.start_date, '%Y-%m-%d').date()
        before_date = datetime.datetime.strptime(args.end_date, '%Y-%m-%d').date()
    except ValueError:
        parser.error('Invalid date format. Please use YYYY-MM-DD.')

    fetch_individual_metrics(args.apikey, after_date, before_date, args.filepath)

