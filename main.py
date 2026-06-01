from playwright.sync_api import sync_playwright
from parser import *
from datetime import datetime

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

    browser = p.chromium.launch(
        channel="chrome",
        headless=False,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--blink-settings=imagesEnabled=false",
        ],
    )

    context = browser.new_context(
        permissions=["geolocation"],
        geolocation={"latitude": 37.7749, "longitude": -122.4194} # Optional: Mock coordinates
    )
 
    context.on("response", parser)

    page = context.new_page()
    page.goto(hotel_list_url)
    page.wait_for_timeout(1000)
    page.locator("a.hotelName").first.click()
    page.wait_for_timeout(2000)
    print("load....")
    end_time = datetime.now()
    print("------------------",end_time-start_time)
    # import time
    # for _ in range(30):
    #     if captured:
    #         break
    #     time.sleep(0.5)

    # if not captured:
    #     print("api not found")
    #     page.wait_for_timeout(8000)

    browser.close()
    print("Done")

