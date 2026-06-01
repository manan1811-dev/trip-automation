from playwright.sync_api import sync_playwright
import json


def extract_bedroom_data(raw):
    """
    Parse Trip.com getHotelRoomListOversea response and return
    a clean, client-ready dict with all room / rate info.
    """
    payload = raw.get("data", raw)

    physic_map  = payload.get("physicRoomMap", {})   
    sale_map    = payload.get("saleRoomMap",   {})   
    room_list   = payload.get("roomList",      [])    

    # ── 1. Build physical room catalogue ──────────────────────────
    physical_rooms: dict[str, dict] = {}
    for pid, pr in physic_map.items():
        pics = [p.get("url", "") for p in pr.get("pictureInfo", []) if p.get("url")]
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
        pid = str(sr.get("physicalRoomId", ""))
        meal     = sr.get("mealInfo",   {})
        cancel   = sr.get("cancelInfo", {})
        booking  = sr.get("bookingStatusInfo", {})
        payment  = sr.get("paymentInfo", {})
        confirm  = sr.get("confirmInfo", {})
        guests   = sr.get("guestCountInfo", {})
        title    = sr.get("titleInfo",  {})

        rates.append({
            "rate_key": rate_key,
            "room_code": sr.get("roomCode"),
            "physical_room_id": pid,
            "physical_room_name": physical_rooms.get(pid, {}).get("name"),
            "price_INR": payment.get("guranteeAmount"),
            "payment_method": payment.get("paymentTitleNew") or payment.get("subTitle"),
            "meal_included": bool(meal),
            "meal_description": meal.get("title") if meal else "Room only",
            "guest_count": guests.get("guestCount"),
            "child_count": guests.get("childCount", 0),
            "cancellation_policy": cancel.get("simpleDesc") or cancel.get("title"),
            "free_cancellation": cancel.get("type") == 3,     # 3 = free cancel, 5 = non-refundable
            "confirmation_type": confirm.get("title"),
            "available": booking.get("isBooking", False),
            "rooms_remaining": booking.get("remainRoomQuantity"),
            "sold_out": booking.get("isFullRoom", False),
            "offer_label": title.get("title"),
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

    # Sort physical rooms by rank preserved in physicRoomMap
    sorted_rooms = sorted(
        physical_rooms.values(),
        key=lambda r: physic_map.get(str(r["physical_room_id"]), {}).get("physicRank", 99)
    )

    # ── 4. Search metadata ─────────────────────────────────────────
    search = payload.get("searchBoxInfo", {})
    meta = {
        "check_in"      : search.get("checkIn"),
        "check_out"     : search.get("checkOut"),
        "adults"        : search.get("adult"),
        "rooms_queried" : search.get("roomQuantity"),
        "total_rooms_available": payload.get("roomCount"),
    }

    return {
        "search_details" : meta,
        "rooms"          : sorted_rooms,
        "total_rates"    : len(rates),
    }


# ──────────────────────────────────────────────
#  PLAYWRIGHT PARSER
# ──────────────────────────────────────────────

captured = {}   # filled by parser callback

def parser(response):
    """Capture Trip.com room API response."""
    if "getHotelRoomListOversea" not in response.url:
        return

    print("\n================ API FOUND ================\n")
    print(f"URL    : {response.url}")
    print(f"STATUS : {response.status}")

    try:
        raw = response.json()

        # Save raw response
        with open("bedroom.json", "w", encoding="utf-8") as f:
            json.dump(raw, f, indent=4)
        print("\n[✓] Raw JSON saved → bedroom.json")

        # Extract clean data
        clean = extract_bedroom_data(raw)

        # Save client-ready file
        with open("hotel_rooms_clean.json", "w", encoding="utf-8") as f:
            json.dump(clean, f, indent=4, ensure_ascii=False)
        print("[✓] Clean JSON saved → hotel_rooms_clean.json")

        captured.update(clean)
        _print_summary(clean)

    except Exception as e:
        print(f"[ERROR] JSON parse failed: {e}")
        try:
            print(response.text())
        except:
            pass

def _print_summary(data: dict):
    sep = "=" * 60
    print(f"\n{sep}")
    print("  ROOM SUMMARY")
    print(sep)
    meta = data["search_details"]
    print(f"  Check-in  : {meta['check_in']}   Check-out : {meta['check_out']}")
    print(f"  Adults    : {meta['adults']}   Total rooms available: {meta['total_rooms_available']}")
    print()
    for i, room in enumerate(data["rooms"], 1):
        fac = ", ".join(room["facilities"][:4]) or "—"
        price = f"₹{room['cheapest_price_INR']:,.0f}" if room["cheapest_price_INR"] else "N/A"
        print(f"  [{i}] {room['name']}")
        print(f"       Bed       : {room['bed_type']}   Area: {room['area'] or 'N/A'}")
        print(f"       View      : {room['view']}   Smoking: {room['smoking_policy']}")
        print(f"       Wifi      : {room['wifi']}")
        print(f"       Facilities: {fac}")
        print(f"       From      : {price}  ({room['cheapest_offer']})")
        print(f"       Rates     : {len(room['rates'])} options")
        print(f"       Images    : {len(room['images'])} photo(s)")
        print()
    print(sep)


# ──────────────────────────────────────────────
#  CONFIG
# ──────────────────────────────────────────────

city       = "Surat"
city_id    = 60194
country_id = 107
check_in   = "2026-06-20"
check_out  = "2026-07-04"
adults     = 2
rooms      = 1

hotel_list_url = (
    f"https://in.trip.com/hotels/list"
    f"?locale=en-IN"
    f"&lat=-1&lon=-1&coordType=GOOGLE"
    f"&optionName={city}"
    f"&cityId={city_id}"
    f"&checkIn={check_in}"
    f"&checkOut={check_out}"
    f"&adult={adults}"
    f"&crn={rooms}"
    f"&optionid={city_id}"
    f"&optiontype=IntlCity"
    f"&countryId={country_id}"
)

print("\nHOTEL LIST URL:\n", hotel_list_url)


# ──────────────────────────────────────────────
#  MAIN
# ──────────────────────────────────────────────

with sync_playwright() as p:

    browser = p.chromium.launch(
        channel="chrome",
        headless=False,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--blink-settings=imagesEnabled=false",
        ],
    )

    context = browser.new_context(no_viewport=True)

    # Attach listener to context (catches all pages/tabs)
    context.on("response", parser)

    page = context.new_page()
    page.goto(hotel_list_url)

    # Click first hotel card
    page.locator("a.hotelName").first.click()

    print("\nHotel listing loaded – waiting for API...\n")

    # Poll until API data is captured (up to 15 s)
    import time
    for _ in range(30):
        if captured:
            break
        time.sleep(0.5)

    if not captured:
        print("API not captured yet — keeping browser open.")
        page.wait_for_timeout(8000)

    browser.close()
    print("\nDone.hotel_rooms_clean.json")