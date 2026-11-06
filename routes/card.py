# card page and everything you can do to a card:
# rate it, add it to the deck, get a TopDeck Insight, or add a new card

from flask import Blueprint, render_template, request, session, redirect, url_for, abort

import db
import insights
import sources
from helpers import track, signed_in, send_to_signin

cards = Blueprint('cards', __name__)


@cards.route('/card/<int:card_id>')
def card(card_id):
    """Shows a card's page."""
    card = db.get_card(card_id)
    if card is None:
        abort(404)
    track('card_viewed', card_id=card_id, card_name=card['name'],
          category=card['category'], subcategory=card['subcategory'])

    # the user's own rating, if signed in
    my_rating = None
    if signed_in():
        my_rating = db.get_user_rating(session['username'], card_id)

    return render_template('card.html', card=card, my_rating=my_rating,
                           size_info=db.SIZE_INFO.get(card['size'], ''),
                           details=db.get_details(card),
                           insight=insights.get_insight(card_id),
                           # these come from the redirects below, to show a message
                           just_rated=request.args.get('rated'),
                           just_added=request.args.get('added'),
                           insight_error=request.args.get('insight_error'))


@cards.route('/card/<int:card_id>/rate', methods=['POST'])
def rate(card_id):
    """Saves the user's star rating."""
    if not signed_in():
        return send_to_signin(url_for('cards.card', card_id=card_id))
    card = db.get_card(card_id)
    if card is None:
        abort(404)
    if not card['in_deck']:
        abort(400)  # must be added to TopDeck before rating

    # no star picked means 0 stars
    stars = int(request.form.get('stars') or 0)
    # only 0 to 5 stars allowed
    if stars < 0 or stars > 5:
        abort(400)

    db.add_rating(session['username'], card_id, stars)
    track('card_rated', card_id=card_id, card_name=card['name'], stars=stars,
          category=card['category'], subcategory=card['subcategory'])
    return redirect(url_for('cards.card', card_id=card_id, rated=1))


@cards.route('/card/<int:card_id>/add', methods=['POST'])
def add_to_deck(card_id):
    """Add to TopDeck button on a card's page (e.g. a card from a poll)."""
    if not signed_in():
        return send_to_signin(url_for('cards.card', card_id=card_id))
    card = db.get_card(card_id)
    if card is None:
        abort(404)

    if not card['in_deck']:
        db.add_to_deck(card_id)
        track('card_submitted', card_id=card_id, card_name=card['name'], category=card['category'],
              subcategory=card['subcategory'], method='card_page', source=card['source'])
    return redirect(url_for('cards.card', card_id=card_id, added=1))


@cards.route('/suggestion/add', methods=['POST'])
def add_suggestion():
    """Add to TopDeck button on a card that AI search found."""
    # the card details come from hidden form fields, so check them all
    if not signed_in():
        return send_to_signin(request.form.get('next'))

    name = request.form.get('name', '').strip()
    category = request.form.get('category')
    if not name or category not in db.CATEGORIES:
        abort(400)

    subcategory = request.form.get('subcategory')
    if category != 'Sports' or subcategory not in db.SPORTS:
        subcategory = None

    # only allow real https image links
    image_url = request.form.get('image_url', '')
    if not image_url.startswith('https://'):
        image_url = None
    back_image_url = request.form.get('back_image_url', '')
    if not back_image_url.startswith('https://'):
        back_image_url = None

    source = request.form.get('source')
    if source not in ['scryfall', 'tcgdex', 'ai']:
        source = 'ai'

    size = request.form.get('size')
    if size not in db.SIZES:
        size = 'Standard'
    set_or_year = request.form.get('set_or_year', '').strip()

    # card details: Magic and Pokémon come straight from their APIs (not from the form),
    # sports cards from what Claude found
    external_id = request.form.get('external_id') or None
    details_from = {'source': source, 'external_id': external_id}
    for key, label in sources.SPORTS_FIELDS:
        details_from[key] = request.form.get(key, '')
    details = sources.card_details(details_from)

    card_id = db.find_or_add_card(name, category, subcategory, set_or_year,
                                  image_url, source, external_id,
                                  back_image_url=back_image_url, size=size, details=details)

    # remember that this card was right for this search, so Claude does better next time
    insights.save_note(request.form.get('search', ''), f'{name} ({set_or_year}, {size})', right=True)

    track('card_submitted', card_id=card_id, card_name=name, category=category,
          subcategory=subcategory, method='ai_search', source=source, size=size)
    return redirect(url_for('cards.card', card_id=card_id, added=1))


@cards.route('/card/<int:card_id>/insight', methods=['POST'])
def insight(card_id):
    """Get TopDeck Insight button, asks Claude about the card."""
    card = db.get_card(card_id)
    if card is None:
        abort(404)
    try:
        text, was_new = insights.generate_insight(card)
    except Exception as error:  # e.g. bad API key or no internet
        print('TopDeck Insight failed:', error)
        return redirect(url_for('cards.card', card_id=card_id, insight_error=1))

    track('insight_viewed', card_id=card_id, card_name=card['name'], newly_generated=was_new)
    return redirect(url_for('cards.card', card_id=card_id))


@cards.route('/add', methods=['GET', 'POST'])
def add_card():
    """The Add a Card form (card.html with mode='add')."""
    # GET shows the form, POST saves it
    if request.method == 'GET':
        return render_template('card.html', mode='add', categories=db.CATEGORIES, sports=db.SPORTS,
                               sizes=db.SIZES)

    if not signed_in():
        return send_to_signin(url_for('cards.add_card'))

    name = request.form['name'].strip()
    category = request.form['category']
    subcategory = None
    if category == 'Sports':
        subcategory = request.form.get('subcategory')
    set_or_year = request.form.get('set_or_year', '').strip()
    size = request.form.get('size')
    if size not in db.SIZES:
        size = 'Standard'

    card_id = db.add_card(name, category, subcategory, set_or_year, size=size)
    track('card_submitted', card_id=card_id, card_name=name, category=category,
          subcategory=subcategory, method='form', size=size)
    return redirect(url_for('cards.card', card_id=card_id))