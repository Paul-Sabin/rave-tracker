"""
RA.co Scraping Feasibility Test

This script tests whether we can scrape event data from ra.co/events/uk/london
using Playwright with anti-bot detection measures.
"""

import asyncio
import json
from playwright.async_api import async_playwright


async def scrape_ra_events():
    """Attempt to scrape the first 5 events from ra.co London events page."""

    results = {
        "success": False,
        "error": None,
        "events": [],
        "page_title": None,
        "status_code": None
    }

    async with async_playwright() as p:
        # Launch browser with stealth settings
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage"
            ]
        )

        # Create context with realistic browser fingerprint
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="en-GB",
            timezone_id="Europe/London",
            extra_http_headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "en-GB,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Cache-Control": "max-age=0"
            }
        )

        # Remove webdriver property to avoid detection
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });

            // Overwrite the plugins to look more realistic
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });

            // Overwrite languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-GB', 'en-US', 'en']
            });
        """)

        page = await context.new_page()

        try:
            # Navigate to the events page
            print("Navigating to ra.co/events/uk/london...")
            response = await page.goto(
                "https://ra.co/events/uk/london",
                wait_until="domcontentloaded",
                timeout=30000
            )

            results["status_code"] = response.status if response else None
            results["page_title"] = await page.title()

            print(f"Status code: {results['status_code']}")
            print(f"Page title: {results['page_title']}")

            # Check for 403 or captcha
            if response and response.status == 403:
                results["error"] = "403 Forbidden - Access denied"
                print("ERROR: 403 Forbidden")
                return results

            # Check for captcha indicators
            page_content = await page.content()
            captcha_indicators = ["captcha", "challenge", "robot", "verify you are human", "access denied"]
            for indicator in captcha_indicators:
                if indicator.lower() in page_content.lower():
                    results["error"] = f"Captcha/Challenge detected: found '{indicator}'"
                    print(f"ERROR: Captcha detected - found '{indicator}'")
                    # Save the page for debugging
                    await page.screenshot(path="captcha_screenshot.png")
                    return results

            # Wait for event listings to appear
            print("Waiting for event listings to load...")

            # Try multiple possible selectors for event cards
            selectors_to_try = [
                "[data-testid='event-listing']",
                "[data-testid='event-item']",
                "article[class*='event']",
                "div[class*='EventCard']",
                "a[href*='/events/']",
                "[class*='listing']",
                "li[class*='event']"
            ]

            found_selector = None
            for selector in selectors_to_try:
                try:
                    await page.wait_for_selector(selector, timeout=5000)
                    found_selector = selector
                    print(f"Found events with selector: {selector}")
                    break
                except:
                    continue

            if not found_selector:
                # Take a screenshot and save HTML for debugging
                await page.screenshot(path="debug_screenshot.png")
                with open("debug_page.html", "w", encoding="utf-8") as f:
                    f.write(page_content)
                print("Could not find event listings. Saved debug files.")
                results["error"] = "Could not find event listings with any known selector"
                return results

            # Extract event data
            print("Extracting event data...")
            events = await page.evaluate("""
                () => {
                    const events = [];

                    // Try to find event cards - ra.co uses various structures
                    // Look for links that contain event information
                    const eventLinks = document.querySelectorAll('a[href*="/events/"]');
                    const seenEvents = new Set();

                    for (const link of eventLinks) {
                        // Skip if this is a navigation link, not an event card
                        if (link.href.includes('/events/uk/') ||
                            link.href.includes('/events/us/') ||
                            link.href.match(/\\/events\\/[a-z]{2}\\/$/)) {
                            continue;
                        }

                        // Extract event ID from URL to avoid duplicates
                        const eventMatch = link.href.match(/\\/events\\/(\\d+)/);
                        if (!eventMatch) continue;

                        const eventId = eventMatch[1];
                        if (seenEvents.has(eventId)) continue;
                        seenEvents.add(eventId);

                        // Try to find the event card container
                        let container = link.closest('li') || link.closest('article') || link.closest('div[class*="Card"]') || link;

                        // Extract text content
                        const text = container.innerText || '';
                        const lines = text.split('\\n').filter(l => l.trim());

                        // Try to identify title, date, and artists from the text
                        let title = '';
                        let date = '';
                        let artists = '';

                        // The title is usually one of the prominent text elements
                        const titleEl = container.querySelector('h3, h4, [class*="title"], [class*="Title"]');
                        if (titleEl) {
                            title = titleEl.innerText.trim();
                        } else if (lines.length > 0) {
                            title = lines[0];
                        }

                        // Look for date patterns
                        for (const line of lines) {
                            if (line.match(/\\d{1,2}\\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)/i) ||
                                line.match(/(Mon|Tue|Wed|Thu|Fri|Sat|Sun)/i) ||
                                line.match(/\\d{1,2}\\/\\d{1,2}/)) {
                                date = line.trim();
                                break;
                            }
                        }

                        // Artists might be in a specific element or after the title
                        const artistEl = container.querySelector('[class*="artist"], [class*="Artist"], [class*="lineup"], [class*="Lineup"]');
                        if (artistEl) {
                            artists = artistEl.innerText.trim();
                        }

                        if (title || date) {
                            events.push({
                                title: title,
                                date: date,
                                artists: artists,
                                url: link.href,
                                raw_text: lines.slice(0, 5).join(' | ')
                            });
                        }

                        if (events.length >= 5) break;
                    }

                    return events;
                }
            """)

            results["events"] = events
            results["success"] = len(events) > 0

            if not events:
                # Additional debugging - save page structure
                await page.screenshot(path="no_events_screenshot.png")
                with open("no_events_page.html", "w", encoding="utf-8") as f:
                    f.write(await page.content())
                results["error"] = "Page loaded but could not extract event data"

            print(f"Successfully extracted {len(events)} events")

        except Exception as e:
            results["error"] = str(e)
            print(f"ERROR: {e}")
            try:
                await page.screenshot(path="error_screenshot.png")
            except:
                pass

        finally:
            await browser.close()

    return results


async def main():
    print("=" * 60)
    print("RA.co Scraping Feasibility Test")
    print("=" * 60)
    print()

    results = await scrape_ra_events()

    print()
    print("=" * 60)
    print("RESULTS")
    print("=" * 60)

    if results["success"]:
        print("SUCCESS! Scraping is feasible.")
        print()
        print("Events found:")
        for i, event in enumerate(results["events"], 1):
            print(f"\n--- Event {i} ---")
            print(f"  Title: {event.get('title', 'N/A')}")
            print(f"  Date: {event.get('date', 'N/A')}")
            print(f"  Artists: {event.get('artists', 'N/A')}")
            print(f"  URL: {event.get('url', 'N/A')}")
    else:
        print("FAILED - Scraping may not be feasible")
        print(f"Error: {results.get('error', 'Unknown error')}")
        print(f"Status code: {results.get('status_code')}")
        print(f"Page title: {results.get('page_title')}")

    # Save results to JSON
    with open("test_output.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print()
    print("Results saved to test_output.json")


if __name__ == "__main__":
    asyncio.run(main())
