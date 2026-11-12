# card page and everything you can do to a card:
# card page and everything you can do to a card:
# rate it, add it to the deck, get a TopDeck Insight, or add a new card

import os
import re
import uuid

from flask import Blueprint, render_template, request, session, redirect, url_for, abort, Response, current_app

import db
import insights
import sources
from helpers import track, signed_in, send_to_signin

cards = Blueprint('cards', __name__)


# a sports picture link: /sports-image/ + a CardSight card id (letters, numbers, dashes)
SPORTS_IMAGE = re.compile(r'/sports-image/[0-9a-fA-F-]{36}')


@cards.route('/sports-image/<card_id>')
def sports_image(card_id):
    """Sends a sports card's picture from CardSight. The API key stays on the server."""
    if not SPORTS_IMAGE.fullmatch('/sports-image/' + card_id):
        abort(404)
    image = sources.sports_image(card_id)
    if image is None:
        abort(404)  # the page shows the letter placeholder instead
    picture, content_type = image
    # browsers may keep it for an hour, short-term like CardSight's terms allow
    return Response(picture, mimetype=content_type, headers={'Cache-Control': 'private, max-age=3600'})


# Magic mana symbols in words
MANA_WORDS = {'W': 'White', 'U': 'Blue', 'B': 'Black', 'R': 'Red', 'G': 'Green',
              'C': 'Colorless', 'S': 'Snow', 'X': 'X', 'P': 'Phyrexian'}


def readable_mana(cost):
    """'{2}{U}{U}' -> '2 · Blue · Blue (4 total)'. '{0}' -> '0'. Double-sided: '{1}{U} // {3}' keeps both."""
    sides = []
    for side in cost.split(' // '):
        symbols = re.findall(r'\{([^}]+)\}', side)
        words, total = [], 0
        for symbol in symbols:
            if symbol.isdigit():
                words.append(symbol)
                total += int(symbol)
            else:
                # hybrid like W/U -> White/Blue
                words.append('/'.join(MANA_WORDS.get(part, part) for part in symbol.split('/')))
                if symbol != 'X':
                    total += 1
        text = ' · '.join(words) or side
        if len(symbols) > 1:
            text += f' ({total} total)'
        sides.append(text)
    return ' // '.join(sides)


def split_set_year(set_or_year):
    """'Topps Base Set (1995) · #3' -> ('Topps Base Set · #3', '1995'). No year found: (text, None)."""
    text = set_or_year or ''
    match = re.search(r'\(?\b(1[89]\d\d|20\d\d)\b\)?', text)
    if not match:
        return text, None
    rest = (text[:match.start()] + ' ' + text[match.end():]).split()
    return ' '.join(rest).strip(' ·'), match.group(1)


def back_image(card):
    """The picture for the back of a card, or None if it can't flip.
    Only Magic flips: Scryfall has every card's back (its other face, or its printed back).
    No API has Pokémon or sports backs."""
    if card['category'] == 'Magic' and card['back_image_url']:
        return card['back_image_url']
    return None


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

    # the "← Back" link: the search or page they came from, or the card's category
    back_url = url_for('pages.browse', category=card['category'])
    back_label = card['category']
    if session.get('back_to') and session['back_to'][0].startswith('/'):
        back_url, back_label = session['back_to']

    details = db.get_details(card)
    # Magic mana cost in plain words: {2}{U}{U} -> 2 · Blue · Blue (4 total)
    details = [[label, readable_mana(value) if label == 'Mana cost' else value] for label, value in details]
    set_text = card['set_or_year']
    team_from_ai = False

    # the kind of big Magic card (Planechase, Commander display...) goes on the Size line instead
    size_kind = None
    for label, value in details:
        if label == 'Oversized type':
            size_kind = value
    details = [d for d in details if d[0] != 'Oversized type']

    # sports cards always show the same rows: Set, Year, Team, Position
    if card['category'] == 'Sports':
        set_text, year = split_set_year(card['set_or_year'])
        saved = dict(details)                   # what Claude found when the card was added
        live = {}
        if card['source'] == 'cardsight' and card['external_id']:
            live = sources.sports_details(card['external_id'])   # loaded live (CardSight's terms)
        details = [['Year', year or 'Unknown']]
        for label in ['Team', 'Position']:
            if live.get(label):
                details.append([label, live[label]])
            elif saved.get(label):
                details.append([label, saved[label]])
                team_from_ai = True
            else:
                details.append([label, 'Unknown'])
        set_text = set_text or 'Unknown'

    return render_template('card.html', card=card, my_rating=my_rating, back_image=back_image(card),
                           size_info=db.SIZE_INFO.get(card['size'], ''), size_kind=size_kind,
                           details=details, set_text=set_text, team_from_ai=team_from_ai,
                           back_url=back_url, back_label=back_label,
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

    # only allow real https image links, or TopDeck's own sports picture route
    image_url = request.form.get('image_url', '')
    if not image_url.startswith('https://') and not SPORTS_IMAGE.fullmatch(image_url):
        image_url = None
    back_image_url = request.form.get('back_image_url', '')
    if not back_image_url.startswith('https://'):
        back_image_url = None

    source = request.form.get('source')
    if source not in ['scryfall', 'tcgdex', 'cardsight', 'ai']:
        source = 'ai'

    size = request.form.get('size')
    if size not in db.sizes_for(category):
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


# photos people upload on the Add a Card page
PHOTO_TYPES = {'jpg', 'jpeg', 'png', 'webp', 'gif'}
MAX_PHOTO_SIZE = 5 * 1024 * 1024  # 5 MB


def is_image(data):
    """True if the file really is a picture (checks its first bytes, not just its name)."""
    return (data.startswith(b'\xff\xd8\xff')                          # jpg
            or data.startswith(b'\x89PNG')                               # png
            or data.startswith((b'GIF87a', b'GIF89a'))                   # gif
            or (data.startswith(b'RIFF') and data[8:12] == b'WEBP'))    # webp


def save_photo(photo):
    """Saves an uploaded photo in static/uploads with a random name.
    Returns (its link, None), or (None, an error message for the form)."""
    extension = photo.filename.rsplit('.', 1)[-1].lower() if '.' in photo.filename else ''
    if extension not in PHOTO_TYPES:
        return None, 'Photos must be a JPG, PNG, WEBP, or GIF.'
    data = photo.read(MAX_PHOTO_SIZE + 1)
    if len(data) > MAX_PHOTO_SIZE:
        return None, 'That photo is too big. The limit is 5 MB.'
    if not is_image(data):
        return None, "That file isn't a picture."

    # a random name, so uploads can't overwrite each other or other files
    folder = os.path.join(current_app.static_folder, 'uploads')
    os.makedirs(folder, exist_ok=True)
    file_name = uuid.uuid4().hex + '.' + extension
    with open(os.path.join(folder, file_name), 'wb') as f:
        f.write(data)
    return url_for('static', filename='uploads/' + file_name), None


def add_form(error=None):
    """The Add a Card form. If there's an error, what they typed is kept (from request.form)."""
    return render_template('card.html', mode='add', categories=db.CATEGORIES, sports=db.SPORTS,
                           sizes=db.SIZES, sizes_by_category=db.SIZES_BY_CATEGORY, error=error)


@cards.route('/add', methods=['GET', 'POST'])
def add_card():
    """The Add a Card form (card.html with mode='add')."""
    # GET shows the form, POST saves it
    if request.method == 'GET':
        return add_form()

    if not signed_in():
        return send_to_signin(url_for('cards.add_card'))

    name = request.form['name'].strip()
    category = request.form['category']
    subcategory = None
    if category == 'Sports':
        subcategory = request.form.get('subcategory')
    set_or_year = request.form.get('set_or_year', '').strip()
    size = request.form.get('size')
    if size not in db.sizes_for(category):
        size = 'Standard'

    # optional photo of the card
    image_url = None
    photo = request.files.get('photo')
    if photo and photo.filename:
        image_url, error = save_photo(photo)
        if error:
            return add_form(error)

    card_id = db.add_card(name, category, subcategory, set_or_year, image_url=image_url, size=size)
    track('card_submitted', card_id=card_id, card_name=name, category=category,
          subcategory=subcategory, method='form', size=size, has_photo=image_url is not None)
    return redirect(url_for('cards.card', card_id=card_id))