"""
RA.co GraphQL API Explorer

Explores the available data fields and query options from the ra.co GraphQL API.
"""

import json
import requests
from datetime import datetime, timedelta


ENDPOINT = "https://ra.co/graphql"
HEADERS = {
    "Content-Type": "application/json",
    "Referer": "https://ra.co/events/uk/london",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def make_request(query, variables, operation_name):
    """Make a GraphQL request and return the response."""
    payload = {
        "operationName": operation_name,
        "query": query,
        "variables": variables
    }
    response = requests.post(ENDPOINT, json=payload, headers=HEADERS, timeout=30)
    return response.json()


def explore_event_listings():
    """Explore all available fields in event listings."""
    print("=" * 70)
    print("EXPLORING EVENT LISTINGS - ALL AVAILABLE FIELDS")
    print("=" * 70)

    # Request as many fields as possible (fixed field names)
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
                    content
                    attending
                    isTicketed
                    queueItEnabled
                    flyerFront
                    images {
                        id
                        filename
                        alt
                        type
                        crop
                    }
                    venue {
                        id
                        name
                        contentUrl
                        address
                        live
                        area {
                            id
                            name
                            urlName
                            country {
                                id
                                name
                                urlCode
                            }
                        }
                    }
                    artists {
                        id
                        name
                        contentUrl
                    }
                    promoters {
                        id
                        name
                        contentUrl
                    }
                    pick {
                        id
                        blurb
                    }
                    cost
                    minimumAge
                    genres {
                        id
                        name
                    }
                }
            }
            filterOptions {
                genre {
                    label
                    value
                }
            }
            totalResults
        }
    }
    """

    start_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    end_date = start_date + timedelta(days=7)

    variables = {
        "filters": {
            "areas": {"eq": 13},  # London
            "listingDate": {
                "gte": start_date.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                "lte": end_date.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            }
        },
        "filterOptions": {"genre": True},
        "page": 1,
        "pageSize": 3
    }

    result = make_request(query, variables, "GET_EVENT_LISTINGS")

    if "errors" in result:
        print(f"GraphQL Errors: {json.dumps(result['errors'], indent=2)}")
        return result

    print(f"\nTotal events available: {result['data']['eventListings']['totalResults']}")

    # Print full structure of first event
    if result['data']['eventListings']['data']:
        print("\n--- FULL EVENT STRUCTURE (first event) ---")
        print(json.dumps(result['data']['eventListings']['data'][0], indent=2))

    # Print available genres
    genres = result['data']['eventListings'].get('filterOptions', {}).get('genre', [])
    if genres:
        print("\n--- AVAILABLE GENRES ---")
        for g in genres:
            print(f"  {g['value']}: {g['label']}")

    return result


def explore_single_event(event_id):
    """Try to get detailed info for a single event."""
    print("\n" + "=" * 70)
    print(f"EXPLORING SINGLE EVENT (ID: {event_id})")
    print("=" * 70)

    # Try different query patterns
    queries_to_try = [
        # Pattern 1: event by ID
        ("""
        query GET_EVENT($id: ID!) {
            event(id: $id) {
                id
                title
                date
                startTime
                endTime
                content
                contentUrl
                attending
                cost
                minimumAge
                venue {
                    id
                    name
                    address
                }
                artists {
                    id
                    name
                }
            }
        }
        """, {"id": str(event_id)}, "GET_EVENT"),
    ]

    for query, variables, op_name in queries_to_try:
        print(f"\nTrying {op_name}...")
        result = make_request(query, variables, op_name)
        if "errors" not in result and result.get("data"):
            print(f"SUCCESS with {op_name}:")
            print(json.dumps(result['data'], indent=2))
            return result
        else:
            errors = result.get("errors", [])
            if errors:
                print(f"  Error: {errors[0].get('message', 'Unknown')[:100]}")

    return None


def explore_areas():
    """Try to discover available areas/cities."""
    print("\n" + "=" * 70)
    print("EXPLORING AREAS/REGIONS")
    print("=" * 70)

    # Query for popular areas which includes more cities
    query = """
    query GET_AREAS {
        areas {
            id
            name
            urlName
            country {
                id
                name
                urlCode
            }
        }
    }
    """

    result = make_request(query, {}, "GET_AREAS")
    if "errors" not in result and result.get("data"):
        areas = result['data']['areas']
        print(f"\nFound {len(areas)} areas")

        # Group by country
        by_country = {}
        for area in areas:
            country = area['country']['name'] if area.get('country') else 'Unknown'
            if country not in by_country:
                by_country[country] = []
            by_country[country].append(area)

        for country, country_areas in sorted(by_country.items()):
            print(f"\n{country}:")
            for a in country_areas[:10]:
                print(f"  ID {a['id']}: {a['name']} ({a['urlName']})")
            if len(country_areas) > 10:
                print(f"  ... and {len(country_areas) - 10} more")

        return result
    else:
        print(f"Error: {result.get('errors', 'Unknown')}")
        return None


def explore_artist(artist_id):
    """Try to get artist details."""
    print("\n" + "=" * 70)
    print(f"EXPLORING ARTIST (ID: {artist_id})")
    print("=" * 70)

    query = """
    query GET_ARTIST($id: ID!) {
        artist(id: $id) {
            id
            name
            contentUrl
            content
            followers
            country {
                id
                name
            }
            genres {
                id
                name
            }
            images {
                filename
            }
        }
    }
    """

    result = make_request(query, {"id": str(artist_id)}, "GET_ARTIST")
    if "errors" not in result and result.get("data"):
        print("SUCCESS:")
        print(json.dumps(result['data'], indent=2))
    else:
        print(f"Errors: {result.get('errors', 'Unknown error')}")

    return result


def explore_venue(venue_id):
    """Try to get venue details."""
    print("\n" + "=" * 70)
    print(f"EXPLORING VENUE (ID: {venue_id})")
    print("=" * 70)

    query = """
    query GET_VENUE($id: ID!) {
        venue(id: $id) {
            id
            name
            contentUrl
            content
            address
            live
            followers
            area {
                id
                name
            }
            images {
                filename
            }
        }
    }
    """

    result = make_request(query, {"id": str(venue_id)}, "GET_VENUE")
    if "errors" not in result and result.get("data"):
        print("SUCCESS:")
        print(json.dumps(result['data'], indent=2))
    else:
        print(f"Errors: {result.get('errors', 'Unknown error')}")

    return result


def explore_filters():
    """Test different filter options."""
    print("\n" + "=" * 70)
    print("EXPLORING FILTER OPTIONS")
    print("=" * 70)

    query = """
    query GET_EVENT_LISTINGS($filters: FilterInputDtoInput, $filterOptions: FilterOptionsInputDtoInput, $page: Int, $pageSize: Int) {
        eventListings(filters: $filters, filterOptions: $filterOptions, page: $page, pageSize: $pageSize) {
            totalResults
            data {
                event {
                    title
                    genres {
                        name
                    }
                }
            }
        }
    }
    """

    start_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    end_date = start_date + timedelta(days=30)

    # Test genre filter (string values based on genre IDs)
    filters_to_try = [
        ("No genre filter", {}),
        ("Techno (genre: '1')", {"genre": {"eq": "1"}}),
        ("House (genre: '2')", {"genre": {"eq": "2"}}),
        ("Drum & Bass (genre: '3')", {"genre": {"eq": "3"}}),
    ]

    base_filter = {
        "areas": {"eq": 13},
        "listingDate": {
            "gte": start_date.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "lte": end_date.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        }
    }

    for name, extra_filter in filters_to_try:
        filters = {**base_filter, **extra_filter}
        variables = {
            "filters": filters,
            "filterOptions": {"genre": True},
            "page": 1,
            "pageSize": 3
        }

        result = make_request(query, variables, "GET_EVENT_LISTINGS")
        if "errors" not in result:
            total = result['data']['eventListings']['totalResults']
            print(f"\n{name}: {total} events")
            for e in result['data']['eventListings']['data'][:2]:
                genres = [g['name'] for g in e['event'].get('genres', [])]
                print(f"  - {e['event']['title'][:50]} [{', '.join(genres)}]")
        else:
            print(f"\n{name}: ERROR - {result['errors'][0].get('message', '')[:80]}")


def explore_introspection():
    """Try to get schema info via introspection."""
    print("\n" + "=" * 70)
    print("EXPLORING SCHEMA (INTROSPECTION)")
    print("=" * 70)

    # Try to get available query types
    query = """
    query IntrospectionQuery {
        __schema {
            queryType {
                fields {
                    name
                    description
                }
            }
        }
    }
    """

    result = make_request(query, {}, "IntrospectionQuery")
    if "errors" not in result and result.get("data"):
        print("Available queries:")
        fields = result['data']['__schema']['queryType']['fields']
        for f in fields:
            desc = f.get('description', '')[:60] if f.get('description') else ''
            print(f"  - {f['name']}: {desc}")
        return result
    else:
        print(f"Introspection disabled or error: {result.get('errors', [{}])[0].get('message', 'Unknown')[:80]}")
        return None


def main():
    all_data = {}

    print("RA.co GraphQL API Explorer")
    print("=" * 70)

    # 0. Try introspection first
    explore_introspection()

    # 1. Explore event listings with all fields
    event_result = explore_event_listings()
    if event_result and "data" in event_result:
        all_data['event_listing_sample'] = event_result['data']['eventListings']['data'][0]
        all_data['genres'] = event_result['data']['eventListings'].get('filterOptions', {}).get('genre', [])

    # Get IDs from first event for further exploration
    if event_result and "data" in event_result:
        first_event = event_result['data']['eventListings']['data'][0]['event']
        event_id = first_event['id']

        # Get artist and venue IDs if available
        artist_id = first_event['artists'][0]['id'] if first_event.get('artists') else None
        venue_id = first_event['venue']['id'] if first_event.get('venue') else None

        # 2. Explore single event endpoint
        event_detail = explore_single_event(event_id)
        if event_detail:
            all_data['single_event'] = event_detail.get('data', {}).get('event')

        # 3. Explore artist endpoint
        if artist_id:
            artist_result = explore_artist(artist_id)
            if artist_result and "data" in artist_result:
                all_data['artist_sample'] = artist_result['data']['artist']

        # 4. Explore venue endpoint
        if venue_id:
            venue_result = explore_venue(venue_id)
            if venue_result and "data" in venue_result:
                all_data['venue_sample'] = venue_result['data']['venue']

    # 5. Explore areas
    areas_result = explore_areas()
    if areas_result and "data" in areas_result:
        all_data['areas'] = areas_result['data']['areas']

    # 6. Explore filter options
    explore_filters()

    # Save all discovered data
    with open("api_exploration.json", "w", encoding="utf-8") as f:
        json.dump(all_data, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 70)
    print("EXPLORATION COMPLETE - Data saved to api_exploration.json")
    print("=" * 70)


if __name__ == "__main__":
    main()
