"""
RA.co GraphQL API Explorer - Part 2
Additional exploration to clarify genres and areas.
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
    payload = {
        "operationName": operation_name,
        "query": query,
        "variables": variables
    }
    response = requests.post(ENDPOINT, json=payload, headers=HEADERS, timeout=30)
    return response.json()


def test_genre_filters():
    """Test genre filters with different formats."""
    print("=" * 70)
    print("TESTING GENRE FILTERS")
    print("=" * 70)

    query = """
    query GET_EVENT_LISTINGS($filters: FilterInputDtoInput, $filterOptions: FilterOptionsInputDtoInput, $page: Int, $pageSize: Int) {
        eventListings(filters: $filters, filterOptions: $filterOptions, page: $page, pageSize: $pageSize) {
            totalResults
            data {
                event {
                    title
                    genres {
                        id
                        name
                    }
                }
            }
        }
    }
    """

    start_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    end_date = start_date + timedelta(days=30)

    base_filter = {
        "areas": {"eq": 13},
        "listingDate": {
            "gte": start_date.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "lte": end_date.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        }
    }

    # Try different genre filter formats based on the values from filterOptions
    filters_to_try = [
        ("genre eq 'techno'", {"genre": {"eq": "techno"}}),
        ("genre eq 'house'", {"genre": {"eq": "house"}}),
        ("genre eq 'drumandbass'", {"genre": {"eq": "drumandbass"}}),
        ("genres contains 'techno'", {"genres": {"contains": "techno"}}),
    ]

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
                genres = [f"{g['name']}(id:{g['id']})" for g in e['event'].get('genres', [])]
                print(f"  - {e['event']['title'][:45]} [{', '.join(genres)}]")
        else:
            print(f"\n{name}: ERROR - {result['errors'][0].get('message', '')[:60]}")


def explore_artist_fixed():
    """Explore artist with correct fields."""
    print("\n" + "=" * 70)
    print("EXPLORING ARTIST (with correct fields)")
    print("=" * 70)

    query = """
    query GET_ARTIST($id: ID!) {
        artist(id: $id) {
            id
            name
            contentUrl
            country {
                id
                name
            }
            image {
                filename
            }
        }
    }
    """

    result = make_request(query, {"id": "11019"}, "GET_ARTIST")  # Maya Jane Coles
    if "errors" not in result and result.get("data"):
        print("Artist data:")
        print(json.dumps(result['data'], indent=2))
    else:
        print(f"Errors: {result.get('errors', 'Unknown')}")
    return result


def explore_venue_fixed():
    """Explore venue with correct fields."""
    print("\n" + "=" * 70)
    print("EXPLORING VENUE (with correct fields)")
    print("=" * 70)

    query = """
    query GET_VENUE($id: ID!) {
        venue(id: $id) {
            id
            name
            contentUrl
            address
            live
            area {
                id
                name
            }
        }
    }
    """

    result = make_request(query, {"id": "2038"}, "GET_VENUE")  # KOKO
    if "errors" not in result and result.get("data"):
        print("Venue data:")
        print(json.dumps(result['data'], indent=2))
    else:
        print(f"Errors: {result.get('errors', 'Unknown')}")
    return result


def explore_area_by_url():
    """Try to get area by URL name."""
    print("\n" + "=" * 70)
    print("EXPLORING AREA BY URL")
    print("=" * 70)

    query = """
    query GET_AREA($id: ID!) {
        area(id: $id) {
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

    # Test known area IDs
    area_ids = ["13", "34", "8", "1", "5"]  # London, Berlin, etc.
    for area_id in area_ids:
        result = make_request(query, {"id": area_id}, "GET_AREA")
        if "errors" not in result and result.get("data") and result['data'].get('area'):
            area = result['data']['area']
            country = area.get('country', {})
            print(f"  ID {area['id']}: {area['name']} ({area['urlName']}) - {country.get('name', 'Unknown')}")


def explore_countries():
    """Get list of countries."""
    print("\n" + "=" * 70)
    print("EXPLORING COUNTRIES")
    print("=" * 70)

    query = """
    query GET_COUNTRIES {
        countries {
            id
            name
            urlCode
        }
    }
    """

    result = make_request(query, {}, "GET_COUNTRIES")
    if "errors" not in result and result.get("data"):
        countries = result['data']['countries']
        print(f"Found {len(countries)} countries:")
        for c in countries[:20]:
            print(f"  ID {c['id']}: {c['name']} ({c['urlCode']})")
        if len(countries) > 20:
            print(f"  ... and {len(countries) - 20} more")
    else:
        print(f"Errors: {result.get('errors', 'Unknown')}")


def explore_search():
    """Try the search endpoint."""
    print("\n" + "=" * 70)
    print("EXPLORING SEARCH")
    print("=" * 70)

    query = """
    query SEARCH($query: String!, $type: [SearchResultType!]) {
        search(query: $query, type: $type) {
            ... on ArtistSearchResult {
                id
                name
                type
            }
            ... on VenueSearchResult {
                id
                name
                type
            }
            ... on EventSearchResult {
                id
                title
                type
            }
        }
    }
    """

    result = make_request(query, {"query": "fabric london", "type": ["VENUE", "EVENT"]}, "SEARCH")
    if "errors" not in result and result.get("data"):
        print("Search results for 'fabric london':")
        for item in result['data']['search'][:10]:
            print(f"  [{item.get('type', 'UNKNOWN')}] {item.get('name') or item.get('title')} (ID: {item['id']})")
    else:
        print(f"Errors: {result.get('errors', 'Unknown')}")


def explore_events_by_artist():
    """Try to get events for a specific artist."""
    print("\n" + "=" * 70)
    print("EXPLORING EVENTS BY ARTIST FILTER")
    print("=" * 70)

    query = """
    query GET_EVENT_LISTINGS($filters: FilterInputDtoInput, $page: Int, $pageSize: Int) {
        eventListings(filters: $filters, page: $page, pageSize: $pageSize) {
            totalResults
            data {
                event {
                    title
                    date
                    venue {
                        name
                    }
                    artists {
                        name
                    }
                }
            }
        }
    }
    """

    start_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    end_date = start_date + timedelta(days=90)

    variables = {
        "filters": {
            "artists": {"eq": 11019},  # Maya Jane Coles
            "listingDate": {
                "gte": start_date.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                "lte": end_date.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            }
        },
        "page": 1,
        "pageSize": 5
    }

    result = make_request(query, variables, "GET_EVENT_LISTINGS")
    if "errors" not in result and result.get("data"):
        total = result['data']['eventListings']['totalResults']
        print(f"Events featuring Maya Jane Coles: {total}")
        for e in result['data']['eventListings']['data']:
            artists = [a['name'] for a in e['event'].get('artists', [])]
            venue = e['event'].get('venue', {}).get('name', 'Unknown')
            print(f"  - {e['event']['title'][:40]} @ {venue}")
            print(f"    Date: {e['event']['date'][:10]}, Artists: {', '.join(artists[:3])}")
    else:
        print(f"Errors: {result.get('errors', 'Unknown')}")


def main():
    test_genre_filters()
    explore_artist_fixed()
    explore_venue_fixed()
    explore_area_by_url()
    explore_countries()
    explore_search()
    explore_events_by_artist()

    print("\n" + "=" * 70)
    print("EXPLORATION COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
