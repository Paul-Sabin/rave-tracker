"""
RA.co GraphQL API Test

Tests the undocumented GraphQL API at ra.co/graphql
"""

import json
import requests
from datetime import datetime, timedelta


def fetch_events():
    """Fetch events from ra.co GraphQL API."""

    endpoint = "https://ra.co/graphql"

    headers = {
        "Content-Type": "application/json",
        "Referer": "https://ra.co/events/uk/london",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    # Date range: today + 7 days
    start_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    end_date = start_date + timedelta(days=7)

    query = """
    query GET_EVENT_LISTINGS($filters: FilterInputDtoInput, $filterOptions: FilterOptionsInputDtoInput, $page: Int, $pageSize: Int) {
        eventListings(filters: $filters, filterOptions: $filterOptions, page: $page, pageSize: $pageSize) {
            data {
                id
                listingDate
                event {
                    id
                    title
                    date
                    startTime
                    endTime
                    contentUrl
                    images {
                        filename
                    }
                    venue {
                        id
                        name
                        contentUrl
                        area {
                            name
                        }
                    }
                    artists {
                        id
                        name
                    }
                    attending
                    pick {
                        blurb
                    }
                }
            }
            totalResults
        }
    }
    """

    variables = {
        "filters": {
            "areas": {"eq": 13},  # 13 = London
            "listingDate": {
                "gte": start_date.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                "lte": end_date.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            }
        },
        "filterOptions": {
            "genre": True
        },
        "page": 1,
        "pageSize": 10
    }

    payload = {
        "operationName": "GET_EVENT_LISTINGS",
        "query": query,
        "variables": variables
    }

    print(f"Fetching events from {start_date.date()} to {end_date.date()}...")
    print(f"Endpoint: {endpoint}")
    print()

    try:
        response = requests.post(endpoint, json=payload, headers=headers, timeout=30)

        print(f"Status code: {response.status_code}")

        if response.status_code == 403:
            print("ERROR: 403 Forbidden - API access blocked")
            return {"success": False, "error": "403 Forbidden", "status_code": 403}

        if response.status_code != 200:
            print(f"ERROR: Unexpected status code {response.status_code}")
            print(f"Response: {response.text[:500]}")
            return {"success": False, "error": f"Status {response.status_code}", "status_code": response.status_code}

        data = response.json()

        # Check for GraphQL errors
        if "errors" in data:
            print(f"GraphQL errors: {data['errors']}")
            return {"success": False, "error": data["errors"], "status_code": 200}

        events_data = data.get("data", {}).get("eventListings", {})
        events = events_data.get("data", [])
        total = events_data.get("totalResults", 0)

        print(f"Total events available: {total}")
        print(f"Events fetched: {len(events)}")
        print()

        results = {
            "success": True,
            "total_results": total,
            "events": []
        }

        for event_listing in events[:5]:
            event = event_listing.get("event", {})

            artists = [a.get("name", "") for a in event.get("artists", [])]
            venue = event.get("venue", {})

            event_info = {
                "title": event.get("title", ""),
                "date": event.get("date", ""),
                "start_time": event.get("startTime", ""),
                "venue": venue.get("name", ""),
                "area": venue.get("area", {}).get("name", "") if venue.get("area") else "",
                "artists": artists,
                "attending": event.get("attending", 0),
                "url": f"https://ra.co{event.get('contentUrl', '')}"
            }
            results["events"].append(event_info)

        return results

    except requests.exceptions.RequestException as e:
        print(f"Request error: {e}")
        return {"success": False, "error": str(e)}


def main():
    print("=" * 60)
    print("RA.co GraphQL API Test")
    print("=" * 60)
    print()

    results = fetch_events()

    print("=" * 60)
    print("RESULTS")
    print("=" * 60)

    if results["success"]:
        print("SUCCESS! GraphQL API is accessible.")
        print(f"Total events in date range: {results['total_results']}")
        print()

        for i, event in enumerate(results["events"], 1):
            print(f"--- Event {i} ---")
            print(f"  Title: {event['title']}")
            print(f"  Date: {event['date']}")
            print(f"  Time: {event['start_time']}")
            print(f"  Venue: {event['venue']}")
            print(f"  Area: {event['area']}")
            print(f"  Artists: {', '.join(event['artists'][:5]) if event['artists'] else 'N/A'}")
            print(f"  Attending: {event['attending']}")
            print(f"  URL: {event['url']}")
            print()
    else:
        print("FAILED - API not accessible")
        print(f"Error: {results.get('error')}")

    # Save results
    with open("test_api_output.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print("Results saved to test_api_output.json")


if __name__ == "__main__":
    main()
