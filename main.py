from playwright.sync_api import sync_playwright
import json
import time

# ──────────────────────────────────────────────
#  USER CONFIG — only change these
# ──────────────────────────────────────────────
CITY_NAME  = "Surat"       # plain city name to search
CHECK_IN   = "2026-06-20"
CHECK_OUT  = "2026-07-04"
ADULTS     = 2
CHILDREN   = 0
ROOMS      = 1
# ──────────────────────────────────────────────


# ──────────────────────────────────────────────
#  STEP 1 — Resolve city params via keyword API
# ──────────────────────────────────────────────

def resolve_city_params(city_name: str, check_in: str, check_out: str,
                         adult: int, children: int) -> dict:
    """
    Opens trip.com, types the city name in the search box,
    intercepts the getHotelKeywords API response, and returns
    the full params dict needed to build the hotel-list URL.
    """
    resolved = {}

    def on_response(response):
        if "getHotelKeywords" not in response.url:
            return

        print(f"\n  [API HIT] {response.url[:120]}")
        try:
            jsondata = response.json()

            # Path: data.mainKeywordList.keywords[0]
            keywords = (
                jsondata.get("data", {})
                        .get("mainKeywordList", {})
                        .get("keywords", [])
            )
            # Pick first result whose tripType == "CT" (city), fallback to index 0
            entry = next(
                (k for k in keywords
                 if k.get("keyword", {})
                      .get("keywordContentInfo", {})
                      .get("tripType") == "CT"),
                keywords[0] if keywords else None
            )
            if not entry:
                print("  [WARN] keywords list is empty")
                return

            kci         = entry["keyword"]["keywordContentInfo"]
            control     = entry["controlInfo"]
            filter_data = control["keywordFilterItem"]["data"]
            basic_city  = control["regionInfo"]["basicCityModel"]
            display_city= control["regionInfo"]["displayCityModel"]

            # Coordinates from coordinateItemList
            coord_list  = kci.get("coordinateItemList", [])
            coord_map   = {c["coordinateType"]: c for c in coord_list}
            def coord(ctype):
                c = coord_map.get(ctype, {})
                return c.get("latitude", "-1"), c.get("longitude", "-1")

            blat, blon = coord("BAIDU")
            glat, glon = coord("GAODE")
            golat, golon = coord("GOOGLE")
            nlat, nlon = coord("NORMAL")

            search_coordinate = (
                f"BAIDU_{blat}_{blon}_0"
                f"|GAODE_{glat}_{glon}_0"
                f"|GOOGLE_{golat}_{golon}_0"
                f"|NORMAL_{nlat}_{nlon}_0"
            )

            # Use NORMAL coords for lat/lon (most reliable for Indian cities)
            lat = nlat if nlat != "-1" else golat
            lon = nlon if nlon != "-1" else golon

            city_id    = basic_city["cityId"]
            country_id = basic_city["countryId"]
            province_id= basic_city["provinceId"]
            city_name_en = display_city.get("cityName") or city_name

            resolved.update({
                "city"             : city_id,
                "cityName"         : city_name_en,
                "provinceId"       : province_id,
                "countryId"        : country_id,
                "checkIn"          : check_in,
                "checkOut"         : check_out,
                "lat"              : lat,
                "lon"              : lon,
                "districtId"       : basic_city.get("districtId", 0),
                "barCurr"          : "INR",
                "searchType"       : filter_data.get("type"),
                "searchWord"       : kci.get("keyword"),
                "searchValue"      : (
                    f"{filter_data.get('filterID')}*{filter_data.get('type')}"
                    f"*{filter_data.get('value')}*{filter_data.get('subType')}"
                ),
                "searchCoordinate" : search_coordinate,
                "crn"              : ROOMS,
                "adult"            : adult,
                "children"         : children,
                "searchBoxArg"     : "t",
                "ctm_ref"          : "ix_sb_dl",
                "travelPurpose"    : 0,
                "domestic"         : False,
            })
            print(f"\nCity resolved → {city_name_en}  "
                  f"(cityId={city_id}, countryId={country_id})\n")

        except Exception as e:
            import traceback
            print(f"  [ERROR] on_response: {e}")
            traceback.print_exc()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            channel="chrome",
            headless=False,
            args=["--disable-blink-features=AutomationControlled",
                  "--blink-settings=imagesEnabled=false"],
        )
        context = browser.new_context(no_viewport=True)
        context.on("response", on_response)
        page = context.new_page()

        # Open trip.com hotels page
        page.goto("https://in.trip.com/hotels/?locale=en-IN", wait_until="domcontentloaded")
        page.wait_for_timeout(2000)

        # ── Dismiss any login/sign-up popup that blocks the search box ──
        for close_sel in [
            "button[aria-label='Close']",
            "button[aria-label='close']",
            "[class*='closeBtn']",
            "[class*='close-btn']",
            "[class*='modal'] button",
            "[class*='dialog'] button",
            "[class*='popup'] button",
        ]:
            try:
                btn = page.locator(close_sel).first
                if btn.is_visible(timeout=500):
                    btn.click()
                    print(f"  Dismissed popup via: {close_sel}")
                    page.wait_for_timeout(500)
                    break
            except Exception:
                pass

        # ── Click and type into #destinationInput ──
        search_input = page.locator("#destinationInput")
        search_input.click()
        page.wait_for_timeout(500)
        search_input.fill("")
        search_input.type(city_name, delay=120)
        print(f"  Typed '{city_name}' — waiting for API response...")

        # ── Wait for getHotelKeywords to fire (up to 15 s) ──
        for _ in range(30):
            if resolved:
                break
            time.sleep(0.5)

        # If API fired but we still need to click a suggestion (some flows require it)
        if not resolved:
            print("  API not captured after typing — trying Enter key...")
            search_input.press("Enter")
            for _ in range(20):
                if resolved:
                    break
                time.sleep(0.5)

        browser.close()

    if not resolved:
        raise RuntimeError(
            f"Could not resolve city '{city_name}'. "
            "Check keywords_raw.json if the file was created, "
            "or run debug_dropdown.py again."
        )
    return resolved



# ──────────────────────────────────────────────
#  ROOM DATA EXTRACTOR  (unchanged from original)
# ──────────────────────────────────────────────

def extract_bedroom_data(raw: dict) -> dict:
    payload = raw.get("data", raw)

    physic_map = payload.get("physicRoomMap", {})
    sale_map   = payload.get("saleRoomMap",   {})

    physical_rooms: dict[str, dict] = {}
    for pid, pr in physic_map.items():
        pics       = [p.get("url", "") for p in pr.get("pictureInfo", []) if p.get("url")]
        facilities = [f.get("title", "") for f in pr.get("physicalFacilityList", []) if f.get("title")]
        physical_rooms[str(pid)] = {
            "physical_room_id" : pr.get("id"),
            "name"             : pr.get("name"),
            "bed_type"         : pr.get("bedInfo", {}).get("title"),
            "area"             : pr.get("areaInfo", {}).get("title") if pr.get("areaInfo") else None,
            "view"             : pr.get("windowInfo", {}).get("title"),
            "smoking_policy"   : pr.get("smokeInfo",  {}).get("title"),
            "wifi"             : pr.get("wifiInfo",   {}).get("title"),
            "facilities"       : [f for f in facilities if f],
            "images"           : pics,
        }

    rates: list[dict] = []
    for rate_key, sr in sale_map.items():
        pid     = str(sr.get("physicalRoomId", ""))
        meal    = sr.get("mealInfo",   {})
        cancel  = sr.get("cancelInfo", {})
        booking = sr.get("bookingStatusInfo", {})
        payment = sr.get("paymentInfo", {})
        confirm = sr.get("confirmInfo", {})
        guests  = sr.get("guestCountInfo", {})
        title   = sr.get("titleInfo",  {})
        rates.append({
            "rate_key"            : rate_key,
            "room_code"           : sr.get("roomCode"),
            "physical_room_id"    : pid,
            "physical_room_name"  : physical_rooms.get(pid, {}).get("name"),
            "price_INR"           : payment.get("guranteeAmount"),
            "payment_method"      : payment.get("paymentTitleNew") or payment.get("subTitle"),
            "meal_included"       : bool(meal),
            "meal_description"    : meal.get("title") if meal else "Room only",
            "guest_count"         : guests.get("guestCount"),
            "child_count"         : guests.get("childCount", 0),
            "cancellation_policy" : cancel.get("simpleDesc") or cancel.get("title"),
            "free_cancellation"   : cancel.get("type") == 3,
            "confirmation_type"   : confirm.get("title"),
            "available"           : booking.get("isBooking", False),
            "rooms_remaining"     : booking.get("remainRoomQuantity"),
            "sold_out"            : booking.get("isFullRoom", False),
            "offer_label"         : title.get("title"),
        })

    rates.sort(key=lambda r: r["price_INR"] or float("inf"))

    for pr in physical_rooms.values():
        pid = str(pr["physical_room_id"])
        pr["rates"] = [r for r in rates if r["physical_room_id"] == pid]
        if pr["rates"]:
            pr["cheapest_price_INR"] = pr["rates"][0]["price_INR"]
            pr["cheapest_offer"]     = pr["rates"][0]["offer_label"]
        else:
            pr["cheapest_price_INR"] = None
            pr["cheapest_offer"]     = None

    sorted_rooms = sorted(
        physical_rooms.values(),
        key=lambda r: physic_map.get(str(r["physical_room_id"]), {}).get("physicRank", 99),
    )

    search = payload.get("searchBoxInfo", {})
    meta = {
        "check_in"             : search.get("checkIn"),
        "check_out"            : search.get("checkOut"),
        "adults"               : search.get("adult"),
        "rooms_queried"        : search.get("roomQuantity"),
        "total_rooms_available": payload.get("roomCount"),
    }
    return {"search_details": meta, "rooms": sorted_rooms, "total_rates": len(rates)}


def _print_summary(data: dict):
    sep = "=" * 60
    print(f"\n{sep}\n  ROOM SUMMARY\n{sep}")
    meta = data["search_details"]
    print(f"  Check-in  : {meta['check_in']}   Check-out : {meta['check_out']}")
    print(f"  Adults    : {meta['adults']}   Total rooms available: {meta['total_rooms_available']}\n")
    for i, room in enumerate(data["rooms"], 1):
        fac   = ", ".join(room["facilities"][:4]) or "—"
        price = f"₹{room['cheapest_price_INR']:,.0f}" if room["cheapest_price_INR"] else "N/A"
        print(f"  [{i}] {room['name']}")
        print(f"       Bed       : {room['bed_type']}   Area: {room['area'] or 'N/A'}")
        print(f"       View      : {room['view']}   Smoking: {room['smoking_policy']}")
        print(f"       Wifi      : {room['wifi']}")
        print(f"       Facilities: {fac}")
        print(f"       From      : {price}  ({room['cheapest_offer']})")
        print(f"       Rates     : {len(room['rates'])} options")
        print(f"       Images    : {len(room['images'])} photo(s)\n")
    print(sep)


# ──────────────────────────────────────────────
#  STEP 2 — Scrape hotel rooms with resolved IDs
# ──────────────────────────────────────────────

def scrape_hotel_rooms(params: dict):
    captured = {}

    def parser(response):
        if "getHotelRoomListOversea" not in response.url:
            return
        print("\n-- API FOUND --")
        print(f"URL    : {response.url}")
        print(f"STATUS : {response.status}")
        try:
            raw   = response.json()
            with open("bedroom.json", "w", encoding="utf-8") as f:
                json.dump(raw, f, indent=4)
            print("Raw JSON saved → bedroom.json")

            clean = extract_bedroom_data(raw)
            with open("hotel_rooms_clean.json", "w", encoding="utf-8") as f:
                json.dump(clean, f, indent=4, ensure_ascii=False)
            print("Clean JSON saved → hotel_rooms_clean.json")

            captured.update(clean)
            _print_summary(clean)
        except Exception as e:
            print(f"[ERROR] JSON parse failed: {e}")

    # Build hotel-list URL from resolved params
    hotel_list_url = (
        f"https://in.trip.com/hotels/list"
        f"?locale=en-IN"
        f"&lat={params['lat']}&lon={params['lon']}&coordType=GOOGLE"
        f"&optionName={params['cityName']}"
        f"&cityId={params['city']}"
        f"&checkIn={params['checkIn']}"
        f"&checkOut={params['checkOut']}"
        f"&adult={params['adult']}"
        f"&crn={params['crn']}"
        f"&optionid={params['city']}"
        f"&optiontype=IntlCity"
        f"&countryId={params['countryId']}"
    )
    print("\nHOTEL LIST URL:\n", hotel_list_url)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            channel="chrome",
            headless=False,
            args=["--disable-blink-features=AutomationControlled",
                  "--blink-settings=imagesEnabled=false"],
        )
        context = browser.new_context(no_viewport=True)
        context.on("response", parser)
        page = context.new_page()
        page.goto(hotel_list_url)

        # Click first hotel card
        page.locator("a.hotelName").first.click()
        print("\nHotel listing loaded – waiting for API...\n")

        for _ in range(30):
            if captured:
                break
            time.sleep(0.5)

        if not captured:
            print("API not captured yet — keeping browser open.")
            page.wait_for_timeout(8000)

        browser.close()

    print("\nDone. Output → hotel_rooms_clean.json")


# ──────────────────────────────────────────────
#  MAIN
# ──────────────────────────────────────────────

if __name__ == "__main__":
    print(f"\nResolving city params for: {CITY_NAME!r} …")
    city_params = resolve_city_params(CITY_NAME, CHECK_IN, CHECK_OUT, ADULTS, CHILDREN)

    print("\nCity params resolved:")
    for k, v in city_params.items():
        print(f"   {k}: {v}")

    scrape_hotel_rooms(city_params)