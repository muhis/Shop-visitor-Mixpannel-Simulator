import json
import logging
import random
import sys
import threading
import uuid
import os
from time import sleep
from typing import Any, ClassVar, List, Optional
import pickle
import requests
from mixpanel import Mixpanel  # For typing purposes
from user_agent import generate_navigator

import random_user
from constants import *
from mixpanel_projects import (ACTIVE_PROJECTS, add_user_to_all_projects,
                               charge_user_to_all_projects,
                               set_people_first_purchase,
                               set_people_last_purchase)
from random_user import (generate_random_ip, generate_random_user_properties,
                         random_bool)
from weighted_random import weighted_random_choice

# Logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.INFO)
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)


class BaseShopper(object):
    def __init__(self):
        self.uuid = str(uuid.uuid4())  # type: ignore
        random_device_os = random.choice(DEVICE_OS_CHOICES)
        self.ip_address: str = generate_random_ip()
        generated_technical_data = generate_navigator()
        self.base_properties: dict = {
            'uuid': self.uuid,
            '$ip': self.ip_address,
            'Browser': generated_technical_data['app_code_name'],
            **generated_technical_data,
        }
        self.properties = self.base_properties

    def __repr__(self):
        return "Unregistered User"

    def visit(self, end_point: str, extra: Optional[dict] = None):
        """
        Send mixpannel API a visit metric.
        """
        properties_to_send: dict
        if extra:
            properties_to_send = {**self.properties, **extra}
        else:
            properties_to_send = self.properties
        logger.info('user %s: Accessed %s', self.uuid, end_point)
        for project in ACTIVE_PROJECTS:
            project.track(self.uuid, end_point,
                          properties=properties_to_send)

    def charge(self, amount, cart):
        charge_user_to_all_projects(self, amount, cart)


class UnregisteredShopper(BaseShopper):
    pass


class User(BaseShopper):
    """
    A registered customer.
    """

    def __init__(self, unregistered_shopper: UnregisteredShopper) -> None:
        self.uuid = unregistered_shopper.uuid
        self.ip_address = unregistered_shopper.ip_address
        self.properties = unregistered_shopper.properties
        self.user_properties: dict = generate_random_user_properties()
        self.properties: dict = {
            **self.user_properties, **self.properties
        }
        add_user_to_all_projects(user=self)
        users_pool.append(self)

    def __repr__(self):
        return "Registered User"

    @classmethod
    def register_requester(cls, requester: UnregisteredShopper):
        return cls(unregistered_shopper=requester)


users_pool: List[User] = []


class Visit(object):
    """
    Simple customer of the website. This might be a registered user or a random unregistered user.
    """
    user_journy: List[str] = []

    def __init__(self, user: Optional[User] = None) -> None:
        self.requester = user or pick_random_requester()
        self.empty_cart()

    def empty_cart(self):
        self.user_cart = {key: 0 for key, _ in SHOP_PRODUCTS}

    def generate_steps(self):
        current = 'main'
        user_steps = []
        while current != 'drop':
            user_steps.append(current)
            current = weighted_random_choice(STEPS[current]['next_steps'])
        user_steps.append(current)
        return user_steps

    def commence(self):
        """
        """
        steps = self.generate_steps()
        step_return_value: dict = {}
        for step in steps:
            time_to_sleep = random.choice(range(3, 9))
            # we inject a delay here since real users don't make multithread requests.
            sleep(time_to_sleep)
            step_return_value = self.execute_step(
                step=step, dependency=step_return_value
            )

    def calculate_cost(self):
        total_cost = 0
        for item in PRODUCTS_PRICES.keys():
            item_price = PRODUCTS_PRICES[item]
            line_price = item_price * self.user_cart[item]
            total_cost += line_price
        return total_cost

    def execute_step(self, step: str, dependency: Optional[dict] = None):
        """
        Generate appropriate step add on then execute it.
        dependency can be Products that the user purchased or other choices.
        """
        human_readable_name: str = STEPS[step]['human_readable']  # type:ignore

        step_requirements = STEPS[step].get('requires') or []
        if 'register_user' in step_requirements and type(self.requester) == UnregisteredShopper:
            self.requester = User.register_requester(self.requester)
        generated_params: dict = {}
        for extra_params in STEPS[step].get('generates', []):
            generator = getattr(random_user, f'generate_{extra_params}')
            generated_params.update(
                **{extra_params: generator()}
            )
            if generator == random_user.generate_item_count:
                item_count = generator()
                self.user_cart[dependency['item_name']] += item_count

        if 'cart_content' in step_requirements:
            generated_params.update(
                {**self.user_cart}
            )

        if 'cart_value' in step_requirements:
            generated_params.update(
                {'Cart value': self.calculate_cost()}
            )
        visit_parameters: dict = {}
        if dependency:
            visit_parameters = {**generated_params, **dependency}
        if step != STEP_DROP:
            self.requester.visit(
                end_point=human_readable_name,
                extra=visit_parameters
            )
        if step == STEP_PAY:
            total_cost = self.calculate_cost()
            logger.info(f'user {self.requester.uuid} payed {total_cost}')
            self.requester.charge(total_cost, self.user_cart)
            set_people_first_purchase(self.requester)
            set_people_last_purchase(self.requester)
            self.empty_cart()
        return generated_params


def pick_random_requester() -> BaseShopper:
    is_registered = random_bool()
    requester: BaseShopper
    if len(users_pool) >= MAX_NUMBER_OF_REGISTERED_USERS:
        # No calculation is needed. Return a registered user.
        return random.choice(users_pool)
    new_users_weight = MAX_NUMBER_OF_REGISTERED_USERS - len(users_pool)
    is_chosen_registered = weighted_random_choice(
        [(False, new_users_weight), (True, MAX_NUMBER_OF_REGISTERED_USERS)]
    )

    if is_chosen_registered and users_pool:
        requester = random.choice(users_pool)
    else:
        requester = UnregisteredShopper()
    logger.info(
        'Requester chosen to be %s. %i registration spots left',
        requester, new_users_weight
    )
    return requester


def start_a_visit():
    vi = Visit()
    vi.commence()


def start_script():
    while True:
        users_pool_count = len(users_pool)
        if threading.active_count() < 4 and threading.active_count() >= 0:
            try:
                threading.Thread(target=start_a_visit).start()
            except Exception as err:
                logger.exception(err)
        if len(users_pool) != users_pool_count:
            save_users_pool()


def save_users_pool():
    file_path = os.path.dirname(os.path.abspath(__file__))
    with open(file_path + "\\users_pool.pydmp", 'wb') as opened_file:
        pickle.dump(users_pool, opened_file)


def load_users_pool():
    file_path = os.path.dirname(os.path.abspath(__file__))
    logger.info('Loading users list from %s', file_path)
    users_pool = []
    try:
        with open(file_path + "\\users_pool.pydmp", 'rb') as opened_file:
            users_pool = pickle.load(opened_file)
            logger.info('Loaded %i users to the pool', len(users_pool))
    except FileNotFoundError as error:
        logger.info('No prior users list found. Skipping users load process.')
    return users_pool


if __name__ == '__main__':
    users_pool = load_users_pool()
    start_script()
