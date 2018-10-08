from weighted_random import weighted_random_choice
import requests
import random
import random_user
import uuid
import json
from time import sleep
from user_agent import generate_navigator
import logging
from mixpanel import Mixpanel  # For typing purposes
from mixpanel_projects import ACTIVE_PROJECTS, add_user_to_all_projects, charge_user_to_all_projects
from constants import *
from typing import List, ClassVar, Any, Optional
import sys
import threading
from random_user import generate_random_user_properties
from random_user import generate_random_ip
from random_user import random_bool
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
            time_to_sleep = random.choice(range(1, 3))
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
            self.empty_cart()
        return generated_params


def pick_random_requester() -> BaseShopper:
    is_registered = random_bool()
    requester: BaseShopper
    if is_registered and users_pool:
        requester = random.choice(users_pool)
    else:
        requester = UnregisteredShopper()
    return requester


def start_a_visit():
    vi = Visit()
    vi.commence()


def start_script():
    while True:
        if threading.active_count() < 10 and threading.active_count() >= 0:
            try:
                threading.Thread(target=start_a_visit).start()
            except Exception as err:
                logger.exception(err)


if __name__ == '__main__':
    start_script()
