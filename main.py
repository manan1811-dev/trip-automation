from playwright.sync_api import sync_playwright
from parser import *
from datetime import datetime
from urllib.parse import urljoin

city = input('Enter a city_name:')
check_in = input('Enter a check in date:')
check_out = input('Enter a check out date:')
adutls = input('Enter a adult count:')
children = input('Enter a children count:')
rooms = input('Enter a rooms count:')

data = get_city_detailes(city)

hotel_list_url = (
    f"https://in.trip.com/hotels/list"
    f"?locale=en-IN"
    f"&lat=-1&lon=-1&coordType=GOOGLE"
    f"&optionName={city}"
    f"&cityId={data.get('city')}"
    f"&checkIn={check_in}"
    f"&checkOut={check_out}"
    f"&adult={adutls}"
    f"&crn={rooms}"
    f"&optionid={data.get('city')}"
    f"&optiontype=IntlCity"
    f"&countryId={data.get('countryId')}"
)

print(hotel_list_url)

print("HOTEL LIST URL:", hotel_list_url)

start_time = datetime.now()

with sync_playwright() as p:
    main_url = "https://in.trip.com/"

    browser = p.chromium.launch(
        channel="chrome",
        headless=True,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--blink-settings=imagesEnabled=false",
        ],
    )

    context = browser.new_context(
        permissions=["geolocation"],
        geolocation={"latitude": 37.7749, "longitude": -122.4194}
    )

    page = context.new_page()

    page.goto(hotel_list_url)
    page.wait_for_timeout(1000)

    select_hotel_url = urljoin(
        main_url,
        page.locator("a.hotelName").first.get_attribute("href")
    )

    print("=" * 50)
    print(select_hotel_url)
    print("=" * 50)

    context.on(
        "response",
        lambda response: parser(response, select_hotel_url)
    )

    page.locator("a.hotelName").first.click()

    page.wait_for_timeout(3000)

    print("load....")

    end_time = datetime.now()

    print("------------------", end_time - start_time)

    browser.close()

    print("Done")