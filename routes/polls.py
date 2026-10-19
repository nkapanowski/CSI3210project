# Polls page: see every poll and vote once in each.

from flask import Blueprint, render_template, request, session, redirect, url_for, abort

import db
from helpers import track, signed_in, send_to_signin

polls = Blueprint('polls', __name__)


@polls.route('/polls', methods=['GET', 'POST'])
def polls_page():
    if request.method == 'POST':
        if not signed_in():
            return send_to_signin(url_for('polls.polls_page'))

        poll_id = int(request.form['poll_id'])
        card_id = int(request.form['card_id'])
        if not db.add_vote(session['username'], poll_id, card_id):
            abort(400)  # that card isn't one of this poll's choices

        card = db.get_card(card_id)
        track('poll_voted', poll_id=poll_id, card_id=card_id, card_name=card['name'])
        return redirect(url_for('polls.polls_page') + '#poll-' + str(poll_id))

    track('page_view', page='polls')
    my_votes = {}
    if signed_in():
        my_votes = db.get_user_votes(session['username'])
    return render_template('polls.html', polls=db.get_polls(), my_votes=my_votes)