import json
import requests
from constants import RANDOM_USERS_URL, STEPS, FINNISH_IP_ADDRESSES
from ipaddress import IPv4Address, AddressValueError
from datetime import datetime, date, timedelta
import random
from weighted_random import weighted_random_choice
from constants import SHOP_PRODUCTS
from typing import TYPE_CHECKING, List
if TYPE_CHECKING:
    from main import BaseShopper  # import only in type checking to avoid circular import
    from main import User


def age(birth_date):
    today = date.today()
    y = today.year - birth_date.year
    if today.month < birth_date.month or today.month == birth_date.month and today.day < birth_date.day:
        y -= 1
    return y


def generate_random_user_properties() -> dict:
    result = json.loads(
        requests.get(url=RANDOM_USERS_URL).content
    )['results'][0]
    clean_dob = generate_date_of_birth()
    return_dict = {
        '$first_name': result['name']['first'].title(),
        '$last_name': result['name']['last'].title(),
        'Date of birth': clean_dob.isoformat(),
        'City': result['location']['city'].title(),
        'Postcode': result['location']['postcode'],
        'Latitude': result['location']['coordinates']['latitude'],
        'Longitude': result['location']['coordinates']['longitude'],
        'Gender': result['gender'],
        '$phone': result['phone'],
        '$mobile': result['cell'],
        'Age': age(clean_dob),
        '$email': result['email'],
        'Is registered': True
    }
    return return_dict


def generate_date_of_birth() -> datetime:
    """
    The random generator sends garbage sometimes in DOB. This will insure generating good result.
    """
    start = datetime(1920, 1, 1)
    end = datetime(2001, 1, 1)
    result = start + timedelta(
        # Get a random amount of seconds between `start` and `end`
        seconds=random.randint(0, int((end - start).total_seconds())),
    )
    return datetime(result.year, result.month, result.day)


def generate_random_ip() ->str:
    """
    Generate random IP address. Copied from
    https://codereview.stackexchange.com/questions/200337/random-ip-address-generator
    with some changes to generate valid looking IP addresses.
    """
    start, finish = random.choice(FINNISH_IP_ADDRESSES)
    start = start.split('.')
    finish = finish.split('.')
    result = []
    for octal in start:
        if octal == '0':
            octal = str(random.choice(range(1, 254)))
        result.append(octal)
    return '.'.join(result)


def random_bool() -> bool:
    return random.choice([True, False])


def generate_item_name():
    return weighted_random_choice(SHOP_PRODUCTS)


def generate_item_count():
    return random.choice(range(1, 10))
