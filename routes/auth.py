# sign in and sign out. sign-in is a pop-up (it lives in global.html)

from flask import Blueprint, request, session, redirect, url_for

import db
from helpers import posthog, user_id, safe_next

auth = Blueprint('auth', __name__)


@auth.route('/signin', methods=['GET', 'POST'])
def signin():
    back_to = safe_next(request.args.get('next'))

    if request.method == 'GET':
        # go back to the page they were on, with ?signin=1 so the pop-up opens by itself
        if '?' in back_to:
            return redirect(back_to + '&signin=1')
        return redirect(back_to + '?signin=1')

    username = request.form['username'].strip()
    email = request.form['email'].strip()
    old_id = user_id()  # the random ID PostHog used before they signed in

    session['username'] = username
    session['email'] = email
    db.get_or_create_user(username, email)

    # connect their earlier anonymous clicks to username, and save name & email
    posthog.alias(previous_id=old_id, distinct_id=username)
    posthog.set(distinct_id=username, properties={'name': username, 'email': email})
    posthog.capture('signed_in', distinct_id=username)

    return redirect(back_to)


@auth.route('/signout')
def signout():
    session.pop('username', None)
    session.pop('email', None)
    return redirect(url_for('pages.home'))