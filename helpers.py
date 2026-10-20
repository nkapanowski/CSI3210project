# small helpers shared by the route files

import atexit
import uuid

from flask import session, redirect, url_for
from posthog import Posthog

import config

# PostHog setup
posthog = Posthog(project_api_key=config.POSTHOG_API_KEY, host=config.POSTHOG_HOST)
atexit.register(posthog.shutdown)  # send leftover events when the app stops


def user_id():
    """The username if signed in, otherwise a random id for this visitor."""
    if 'username' in session:
        return session['username']
    if 'anon_id' not in session:
        session['anon_id'] = str(uuid.uuid4())
    return session['anon_id']


def track(event, **properties):
    """Sends an event to PostHog, e.g. track('card_rated', stars=5)."""
    posthog.capture(distinct_id=user_id(), event=event, properties=properties)


def signed_in():
    """True if a user is signed in."""
    return 'username' in session


def safe_next(page):
    """Returns page if it's on TopDeck, otherwise home. Blocks redirects to other sites."""
    if page and page.startswith('/') and not page.startswith('//'):
        return page.rstrip('?')
    return url_for('pages.home')


def send_to_signin(back_to):
    """Sends to sign in, then back to back_to."""
    return redirect(url_for('auth.signin', next=back_to))