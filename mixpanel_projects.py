from mixpanel import Mixpanel
from mixpanel_async import AsyncBufferedConsumer

from constants import MIXPANNEL_TOKENS
from typing import List, ClassVar, Any, Optional
from datetime import datetime
import logging
import sys


logger = logging.getLogger()
logger.setLevel(logging.INFO)

ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.INFO)
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)


def init_mixpannel_clients(mxp_tokens: List[str]) -> List[Mixpanel]:
    """
    Return a list of mixpannel clients.
    """
    projects: List[Mixpanel] = []
    logger.info('Found %s Mixpannel tokens.', len(mxp_tokens))
    for project_token in mxp_tokens:
        mp = Mixpanel(project_token, consumer=AsyncBufferedConsumer())
        projects.append(mp)
    logger.info('%s Mixpannel projects ready to go.', len(projects))
    return projects


def add_user_to_all_projects(user):
    """
    Add a user to all active mixpanel projects.
    """
    for project in ACTIVE_PROJECTS:
        project.people_set(
            user.uuid, user.properties
        )


def charge_user_to_all_projects(user, charge, cart):
    """
    Add a user to all active mixpanel projects.
    """
    for project in ACTIVE_PROJECTS:
        project.people_track_charge(
            user.uuid, charge, cart
        )


def set_people_first_purchase(user):
    """User pay event register the current date as a property. Mixpanel will make sure we don't repeat those

    Arguments:
        user {User} -- The user that payed.
    """
    for project in ACTIVE_PROJECTS:
        project.people_set_once(
            user.uuid, properties={'First purchase': datetime.utcnow()}
        )


def set_people_last_purchase(user):
    """User pay event register the current date as a property. Mixpanel will make sure we don't repeat those

    Arguments:
        user {User} -- The user that payed.
    """
    for project in ACTIVE_PROJECTS:
        project.people_set(
            user.uuid, properties={'Last purchase': datetime.utcnow()}
        )


ACTIVE_PROJECTS = init_mixpannel_clients(mxp_tokens=MIXPANNEL_TOKENS)
