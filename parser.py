from playwright.sync_api import sync_playwright
import json
import requests

def extract_bedroom_data(raw):
    payload = raw.get("data", raw)

    physic_map  = payload.get("physicRoomMap", {})   
    sale_map    = payload.get("saleRoomMap",   {})   
    room_list   = payload.get("roomList",      [])    

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

captured = {}   

def parser(response):
    """Capture Trip.com room API response."""
    if "getHotelRoomListOversea" not in response.url:
        return

    print("\n================ API FOUND ================\n")
    print(f"URL    : {response.url}")
    print(f"STATUS : {response.status}")

    try:
        raw = response.json()


        clean = extract_bedroom_data(raw)

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

def get_city_detailes(city):
    json_data = {
        'code': 0,
        'codeType': '',
        'keyWord': f'{city}',
        'searchType': 'D',
        'scenicCode': 0,
        'cityCodeOfUser': 0,
        'searchConditions': [
            {
                'type': 'D_PROVINCE',
                'value': 'T',
            },
            {
                'type': 'SupportNormalSearch',
                'value': 'T',
            },
            {
                'type': 'DisplayTagIcon',
                'value': 'F',
            },
        ],
        'head': {
            'platform': 'PC',
            'clientId': '1780044424753.a709Z3UkocAu',
            'bu': 'ibu',
            'group': 'TRIP',
            'aid': '',
            'sid': '',
            'ouid': '',
            'currency': 'GBP',
            'region': 'IN',
            'locale': 'en-IN',
            'timeZone': '5.5',
            'device': 'PC',
            'deviceID': 'PC',
            'clientVersion': '0',
            'frontend': {
                'vid': '1780044424753.a709Z3UkocAu',
                'sessionID': '4',
                'pvid': '8',
            },
            'extension': [
                {
                    'name': 'cityId',
                    'value': '',
                },
                {
                    'name': 'checkIn',
                    'value': '',
                },
                {
                    'name': 'checkOut',
                    'value': '',
                },
            ],
            'cid': '1780044424753.a709Z3UkocAu',
            'hotelExtension': {
                'webpSupport': True,
            },
            'traceLogID': 'a30cc3810ebf18',
            'ticket': '',
            'hasAidInUrl': 'false',
            'href': 'https://in.trip.com/?locale=en-in',
        },
    }
    headers = {
        'accept': 'application/json',
        'accept-language': 'en-US,en;q=0.9',
        'content-type': 'application/json',
        'cookieorigin': 'https://in.trip.com',
        'origin': 'https://in.trip.com',
        'priority': 'u=1, i',
        'referer': 'https://in.trip.com/?locale=en-in',
        'sec-ch-ua': '"Chromium";v="148", "Google Chrome";v="148", "Not/A)Brand";v="99"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36',
        # 'cookie': 'GUID=09034103416916845122; UBT_VID=1780044424753.a709Z3UkocAu; ibulanguage=EN; cookiePricesDisplayed=GBP; _RGUID=5bf4b4fb-4630-488c-9e59-ebea199d506a; _abtest_userid=f58b220a-830f-460e-9d9d-24d7a1b5a5bd; _gcl_au=1.1.1829932973.1780044444; _twpid=tw.1780044445642.185128131710031731; ibu_pwa_insvisit=%7B%22vid%22%3A%221780044424753.a709Z3UkocAu%22%2C%22time%22%3A1780045773078%7D; _fbp=fb.1.1780045829219.589662370156194485; _ga_37RNVFDP1J=GS2.2.s1780047715$o1$g0$t1780047715$j60$l0$h0; _ga=GA1.1.53443069.1780045769; ibulocale=en_in; ibu_country=IN; ibu_cookie_strict=0; _tp_search_latest_channel_name=hotels; _fwb=6834xoUO8zvMPrHMfd1Dhc.1780048198673; w_lid=016a1962a753225aa420; nfes_isSupportWebP=1; ibu_hotel_search_crn_guest=%7B%22adult%22%3A2%2C%22children%22%3A0%2C%22ages%22%3A%22%22%2C%22crn%22%3A1%7D; oldCurrency=GBP; ibu_online_jump_site_result={"isShowSuggestion":false}; ubtc_trip_pwa=0; x-ctx-user-recognize=IS_EU; w_tuid=nzcGs5J1FHAqI8dKYrEz0NkJqVo9hZBEBQW7SfgkfpKdjeEa0R3kxbhzhLQRXarrG2sxOd1c1luPKMnEWX8tWi8hKfA7IwgOgXiYYdIIJDsUiTGiG2xYpam4tVSqr6emM61hNkSICszmwlybhzAkzpQPeKiL9LV0P+nGO1Pnh/faKjP7eS4fDl5OUEPJfeIX2A==:1_1_1_1.0zNV1OPFX+CA6O07VsUQ90amcT+KxRhylH3Q7ltTMNo=; IBU_TRANCE_LOG_P=64328600306; ibu_hotel_search_date=%7B%22checkIn%22%3A%222026-06-01%22%2C%22checkOut%22%3A%222026-06-02%22%2C%22isChoseFlexible%22%3Afalse%2C%22flexibleDate%22%3A%7B%22selectNight%22%3A0%7D%2C%22dayFlexibility%22%3A0%7D; ibu_hotel_search_target=%7B%22countryId%22%3A107%2C%22provinceId%22%3A10556%2C%22searchWord%22%3A%22Mumbai%22%2C%22cityId%22%3A724%2C%22searchType%22%3A%22%22%2C%22searchValue%22%3A%22%22%2C%22cityName%22%3A%22Mumbai%22%7D; tncr=0; ibu_online_permission_cls_ct=2; ibu_online_permission_cls_gap=1780289495235; ibu_webpush_scope=%252F; GUID.sig=BjW1rTe9VJJtR_r3IzdV8k4sTAHrDpDfAM30-uGohIY; GUID=09034103416916845122; _resDomain=https%3A%2F%2Faw-s.tripcdn.com; ibusite=IN; ibugroup=trip; IBU_showtotalamt=0; intl_ht1=h4%3D724_112421210%2C495_127688912%2C495_758417; _ga_X437DZ73MR=GS2.1.s1780289075$o5$g1$t1780291023$j60$l0$h0; _bfa=1.1780044424753.a709Z3UkocAu.1.1780290706667.1780291023551.4.8.10320668088; wcs_bt=s_33fb334966e9:1780291025; _uetsid=8f06da805d7411f183c6ab0abf09a142; _uetvid=050fd5805b3b11f18c6d5135257d3c97; g_state={"i_l":0,"i_ll":1780291026821,"i_b":"ReljxP890ookHzh/w40A5P8HiuU34k+PhAqNd/7lwpo","i_e":{"enable_itp_optimization":0},"i_et":1780048199456}',
    }

    
    response = requests.post('https://in.trip.com/htls/getKeywordSearch', headers=headers, json=json_data)

    if response:
        jsondata = response.json()
        firstresult = jsondata.get("keyWordSearchResults")[0]
        search_values = firstresult.get("item").get("data")
        coordinateInfos = firstresult.get("coordinateInfos")
        params = {
            "city" : firstresult.get("city").get("geoCode"),
            "cityName" : firstresult.get("city").get("enusName"),
            "provinceId":firstresult.get("province").get("geoCode"),
            "countryId":firstresult.get("country").get("geoCode"),
            "lat":firstresult.get("coordinateInfos")[0].get("latitude"),
            "lon":firstresult.get("coordinateInfos")[0].get("longitude"),
            "districtId":0,
            "barCurr":"INR",
            "searchType":firstresult.get("resultType"),
            "searchWord":firstresult.get("resultWord"),
            "searchValue":f"{search_values.get("filterID")}*{search_values.get("type")}*{search_values.get("value")}*{search_values.get("subType")}",
            "searchCoordinate":f"BAIDU_{coordinateInfos[0].get("latitude")}_{coordinateInfos[0].get("longitude")}_0|GAODE_{coordinateInfos[1].get("latitude")}_{coordinateInfos[1].get("longitude")}_0|GOOGLE_{coordinateInfos[2].get("latitude")}_{coordinateInfos[2].get("longitude")}_0|NORMAL_{coordinateInfos[3].get("latitude")}_{coordinateInfos[3].get("longitude")}_0",
            "crn":1,
            "searchBoxArg":"t",
            "ctm_ref":"ix_sb_dl",
            "travelPurpose":0,
            "domestic":False
        }

        return params
