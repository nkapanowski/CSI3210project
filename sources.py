# real card details and images from free APIs (no keys needed)
# Scryfall for Magic  (https://scryfall.com/docs/api)
# TCGdex for Pokémon   (https://tcgdex.dev)
# CardSight AI for sports (needs CARDSIGHT_API_KEY in config.py). without a key,
# sports cards use claude's details (no pictures)

# one card name (like "Charizard") has many printings: different sets, numbers, and sizes.
# find_printings() gets the real printings from the API and keeps the ones that match
# what the user asked for (set, year, card number, size).

import re

import time

import requests

import config

# sent with every request so the APIs know who's asking
HEADERS = {'User-Agent': 'TopDeck/1.0 (CSI 3210 class project)', 'Accept': 'application/json'}
TIMEOUT = 6          # seconds, so a slow API doesn't freeze the page
MAX_RESULTS = 250    # safety limit so one search can't load thousands of pictures


###---- Magic (Scryfall) ----###

# Magic's big side-game cards (all about 3.5 x 5 in), by their Scryfall layout
OVERSIZED_KINDS = {'planar': 'Planechase', 'scheme': 'Archenemy', 'vanguard': 'Vanguard'}


def magic_card(card):
    """Turns one Scryfall printing into a TopDeck card dict."""
    # double-sided cards keep a picture on each face (front and back)
    images = card.get('image_uris')
    back_image_url = None
    faces = card.get('card_faces') or []
    if not images and faces:
        images = faces[0].get('image_uris')
        if len(faces) > 1 and faces[1].get('image_uris'):
            back_image_url = faces[1]['image_uris'].get('normal')

    # every other card has a printed back design (usually the classic Magic back).
    # Scryfall gives its id, and keeps a picture of each design
    if not back_image_url and card.get('card_back_id'):
        back_id = card['card_back_id']
        back_image_url = f'https://backs.scryfall.io/large/{back_id[0]}/{back_id[1]}/{back_id}.jpg'
    image_url = None
    if images:
        image_url = images.get('normal')

    set_name = card.get('set_name', '')
    year = (card.get('released_at') or '')[:4]
    number = card.get('collector_number', '')

    # big Magic cards: Scryfall marks them "oversized", or they're a big side-game card
    size = 'Standard'
    if card.get('oversized') or card.get('layout') in OVERSIZED_KINDS:
        size = 'Oversized'

    return {
        'name': card['name'],
        'set_or_year': f'{set_name} ({year}) · #{number}',  # ex. 'Alpha (1993) · #232'
        'set_name': set_name,
        'year': year,
        'number': number,
        'size': size,
        'image_url': image_url,
        'back_image_url': back_image_url,
        'source': 'scryfall',
        'external_id': card['id'],
    }


def magic_printings(name):
    """Every printing of a Magic card, newest first. [] if no card has that name."""
    url = 'https://api.scryfall.com/cards/search'
    # include_extras: also find oversized and side-game cards (planes, schemes, Vanguard)
    params = {'q': '!"' + name + '"', 'unique': 'prints', 'order': 'released', 'dir': 'desc',
              'include_extras': 'true'}
    r = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)

    # no card with that exact name: let Scryfall fix the spelling once, then try again
    if r.status_code == 404:
        fixed = requests.get('https://api.scryfall.com/cards/named', params={'fuzzy': name},
                             headers=HEADERS, timeout=TIMEOUT)
        if fixed.status_code != 200:
            return []
        params['q'] = '!"' + fixed.json()['name'] + '"'
        r = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)

    if r.status_code != 200:
        return []

    # Scryfall sends 175 cards per page, so keep loading pages (up to MAX_RESULTS)
    page = r.json()
    printings = [magic_card(card) for card in page.get('data', [])]
    while page.get('has_more') and len(printings) < MAX_RESULTS:
        r = requests.get(page['next_page'], headers=HEADERS, timeout=TIMEOUT)
        if r.status_code != 200:
            break
        page = r.json()
        printings += [magic_card(card) for card in page.get('data', [])]
    return printings


###---- Pokémon (TCGdex) ----###

# set names by set id, like {'base1': 'Base Set'}. loaded once, then kept in memory
pokemon_sets = {}


def pokemon_set_name(set_id):
    if not pokemon_sets:
        r = requests.get('https://api.tcgdex.net/v2/en/sets', headers=HEADERS, timeout=TIMEOUT)
        if r.status_code == 200:
            for s in r.json():
                pokemon_sets[s['id']] = s['name']
    return pokemon_sets.get(set_id, '')


def pokemon_printings(name):
    """Every card with this Pokémon in its name, newest first: "Charizard" also finds
    Charizard ex, Dark Charizard, Charizard VMAX... [] if there are none."""
    r = requests.get('https://api.tcgdex.net/v2/en/cards', params={'name': name},
                     headers=HEADERS, timeout=TIMEOUT)
    if r.status_code != 200:
        return []
    # TCGdex matches any part of a name ("Mew" would also find "Mewtwo"),
    # so keep only names with the whole word in them
    whole_word = re.compile(r'\b' + re.escape(name) + r'\b', re.IGNORECASE)
    results = [c for c in r.json() if whole_word.search(c.get('name', ''))]

    printings = []
    for c in reversed(results):  # TCGdex lists oldest first
        number = c.get('localId', '')
        # a card id is the set id + '-' + the number, like 'base1-4'
        set_id = c['id'][:-(len(number) + 1)] if number else c['id']
        set_name = pokemon_set_name(set_id)

        image_url = None
        if c.get('image'):
            image_url = c['image'] + '/high.webp'

        printings.append({
            'name': c['name'],
            'set_or_year': f'{set_name} · #{number}',  # ex. 'Base Set · #4'
            'set_name': set_name,
            'year': '',  # TCGdex only has the year on each set's own page
            'number': number,
            'size': 'Standard',  # TCGdex doesn't list jumbo cards
            'image_url': image_url,
            'back_image_url': None,
            'source': 'tcgdex',
            'external_id': c['id'],
        })

    # cards with a picture first
    printings.sort(key=lambda p: p['image_url'] is None)
    return printings


###---- Sports (CardSight AI, free plan: 750 calls a month) ----###
# needs CARDSIGHT_API_KEY in config.py. without a key, sports cards use claude's details instead.
# CardSight's terms only allow keeping their card info and pictures short-term, so nothing
# from CardSight is saved in the database (only the card's CardSight id). results are kept
# in memory for a while instead, which also saves free calls.

CARDSIGHT_API = 'https://api.cardsight.ai/v1'
MAX_SPORTS_CARDS = 8      # most sports cards to show per name, to save free calls
KEEP_FOR = 60 * 60        # seconds to remember CardSight results (1 hour)

# the key is optional, so teammates without one can still run the app
CARDSIGHT_KEY = getattr(config, 'CARDSIGHT_API_KEY', None)

# short-term memory of CardSight results: {key: (time saved, value)}
cardsight_memory = {}


def remembered(key):
    """A saved result if it's still fresh, otherwise None."""
    if key in cardsight_memory:
        saved_at, value = cardsight_memory[key]
        if time.time() - saved_at < KEEP_FOR:
            return value
        del cardsight_memory[key]
    return None


def remember(key, value):
    if len(cardsight_memory) > 300:  # don't let it grow forever
        cardsight_memory.clear()
    cardsight_memory[key] = (time.time(), value)


def cardsight_get(path, params=None):
    """One call to CardSight. Returns the response (or raises if the network fails)."""
    return requests.get(CARDSIGHT_API + path, params=params, headers={'X-API-Key': CARDSIGHT_KEY},
                        timeout=TIMEOUT)


def sports_printings(found):
    """Real sports cards for what Claude found: up to MAX_SPORTS_CARDS, as TopDeck card dicts.
    Returns None if there's no key or CardSight couldn't answer, so the app falls back to Claude."""
    if not CARDSIGHT_KEY:
        return None

    params = {'q': found['name'], 'type': 'card', 'take': MAX_SPORTS_CARDS}
    if found.get('subcategory'):
        params['segment'] = found['subcategory']      # the sport, like "Basketball"
    if found.get('wanted_year'):
        params['year'] = found['wanted_year']
    if found.get('wanted_set'):
        params['q'] += ' ' + found['wanted_set']     # "michael jordan fleer"

    key = ('search', tuple(sorted(params.items())))
    results = remembered(key)
    if results is None:
        r = cardsight_get('/catalog/search', params)
        if r.status_code != 200:
            print('CardSight search failed:', r.status_code)
            return None
        results = r.json().get('results', [])
        remember(key, results)

    cards = []
    for c in results:
        year = c.get('year') or ''
        set_name = ' '.join(x for x in [c.get('releaseName'), c.get('setName')] if x)
        number = c.get('cardNumber') or ''
        set_or_year = set_name
        if year:
            set_or_year = f'{set_name} ({year})'
        if number:
            set_or_year += f' · #{number}'
        cards.append({
            'name': c['name'],
            'set_or_year': set_or_year,                 # ex. 'Fleer Base (1986) · #57'
            'set_name': set_name,
            'year': year,
            'number': number,
            'size': 'Standard',
            'image_url': '/sports-image/' + c['id'],    # TopDeck's own route fetches the picture
            'back_image_url': None,
            'source': 'cardsight',
            'external_id': c['id'],
        })
    return cards


def sports_details(card_id):
    """A sports card's team and position from CardSight, like {'Team': 'Chicago Bulls', 'Position': 'Guard'}.
    Only what CardSight has: {} if it has neither."""
    if not CARDSIGHT_KEY:
        return {}
    details = remembered(('details', card_id))
    if details is not None:
        return details
    try:
        r = cardsight_get('/catalog/cards/' + card_id)
    except requests.RequestException:
        return {}
    if r.status_code != 200:
        return {}

    # CardSight keeps extra info as key/value fields, like {'key': 'TEAM', 'value': 'Chicago Bulls'}
    details = {}
    for field in r.json().get('fields') or []:
        key = (field.get('key') or '').upper()
        if 'TEAM' in key and field.get('value'):
            details['Team'] = field['value']
        elif 'POSITION' in key and field.get('value'):
            details['Position'] = field['value']
    remember(('details', card_id), details)
    return details


def sports_image(card_id):
    """A sports card's picture as (bytes, content type), or None if there isn't one."""
    if not CARDSIGHT_KEY:
        return None
    image = remembered(('image', card_id))
    if image is not None:
        return image
    try:
        r = cardsight_get('/images/cards/' + card_id, {'format': 'raw'})
    except requests.RequestException:
        return None
    if r.status_code != 200:
        return None
    image = (r.content, r.headers.get('Content-Type', 'image/jpeg'))
    remember(('image', card_id), image)
    return image


###---- card details (shown on the card page) ----###

def magic_details(card_id):
    """Type, mana cost, rarity, and artist from Scryfall."""
    r = requests.get('https://api.scryfall.com/cards/' + card_id, headers=HEADERS, timeout=TIMEOUT)
    if r.status_code != 200:
        return []
    card = r.json()
    face = card
    if not card.get('type_line') and card.get('card_faces'):
        face = card['card_faces'][0]  # double-sided: use the front
    # what kind of big card it is, if it's oversized
    kind = OVERSIZED_KINDS.get(card.get('layout'))
    if not kind and card.get('oversized'):
        # other oversized cards are display cards, mostly from Commander decks
        if 'commander' in (card.get('set_name') or '').lower():
            kind = 'Commander display'
        else:
            kind = 'Display card'

    details = [['Oversized type', kind],
               ['Type', card.get('type_line') or face.get('type_line')],
               ['Mana cost', card.get('mana_cost') or face.get('mana_cost')],
               ['Rarity', (card.get('rarity') or '').title()],
               ['Artist', card.get('artist')]]
    return [d for d in details if d[1]]  # skip empty ones


def pokemon_details(card_id):
    """HP, type, stage, rarity, and illustrator from TCGdex."""
    r = requests.get('https://api.tcgdex.net/v2/en/cards/' + card_id, headers=HEADERS, timeout=TIMEOUT)
    if r.status_code != 200:
        return []
    card = r.json()
    details = [['HP', card.get('hp')],
               ['Type', ', '.join(card.get('types') or [])],
               ['Stage', card.get('stage')],
               ['Rarity', card.get('rarity')],
               ['Illustrator', card.get('illustrator')]]
    return [[label, str(value)] for label, value in details if value]


# what Claude can tell us about a sports card, and the label for each
SPORTS_FIELDS = [['team', 'Team'], ['position', 'Position'], ['brand', 'Brand'],
                 ['card_number', 'Card number'], ['rookie', 'Rookie card'], ['key_stats', 'Key stats']]


def card_details(card):
    """The details to save for a card. Magic and Pokémon come from their APIs,
    sports cards from what Claude found. Returns [] if there's nothing."""
    # card ids are letters, numbers, and dashes. anything else came from a tampered form, so skip it
    card_id = card.get('external_id') or ''
    if card_id and not all(ch.isalnum() or ch in '-_.' for ch in card_id):
        return []
    if card.get('source') == 'cardsight':
        # CardSight's terms don't allow saving its card info (the card page loads it live),
        # but Claude's team and position are ours to keep, as a backup
        return [[label, value] for label, value in claude_sports_details(card) if label in ('Team', 'Position')]
    try:
        if card.get('source') == 'scryfall' and card.get('external_id'):
            return magic_details(card['external_id'])
        if card.get('source') == 'tcgdex' and card.get('external_id'):
            return pokemon_details(card['external_id'])
    except requests.RequestException:
        return []  # API down or slow, save the card without details

    return claude_sports_details(card)


def claude_sports_details(card):
    """The sports details Claude found, like [['Team', 'Chicago Bulls'], ['Position', 'Guard']]."""
    details = []
    for key, label in SPORTS_FIELDS:
        value = ' '.join(str(card.get(key) or '').split())[:120]  # one short line
        if value:
            details.append([label, value])
    return details


###---- matching what the user asked for ----###

def matches(printing, wanted):
    """True if the printing fits the set, year, and number the user typed (if they typed any)."""
    want_set = (wanted.get('wanted_set') or '').lower()
    want_year = wanted.get('wanted_year') or ''
    # "4/102" -> "4", and "004" -> "4"
    want_number = (wanted.get('wanted_number') or '').split('/')[0].lstrip('0').lower()

    if want_set and want_set not in printing['set_name'].lower():
        return False
    if want_year and printing['year'] and printing['year'] != want_year:
        return False
    if want_number and printing['number'].lstrip('0').lower() != want_number:
        return False
    return True


def find_printings(found):
    """The real printings for a card Claude found, best matches first.
    Returns (the printings, how many there are)."""
    try:
        if found['category'] == 'Magic':
            printings = magic_printings(found['name'])
        elif found['category'] == 'Pokémon':
            printings = pokemon_printings(found['name'])
        elif found['category'] == 'Sports':
            # CardSight, if there's a key. None (no key, or it failed) or [] (not found)
            # both fall back to Claude's details, since CardSight may not have every card
            printings = sports_printings(found) or None
        else:
            printings = None  # no free API for other cards
    except requests.RequestException:
        printings = None  # API down or slow

    # no API to check with: use Claude's details
    if printings is None:
        card = dict(found)
        card.update({'image_url': None, 'back_image_url': None, 'source': 'ai', 'external_id': None,
                     'size': 'Standard'})  # TODO (Pokémon): pick a jumbo size here when the search asks for jumbo
        return [card], 1

    # the API has no card with this name, so Claude probably got it wrong: skip it
    if not printings:
        return [], 0

    matching = [p for p in printings if matches(p, found)]
    if not matching:
        matching = printings  # nothing fit the set/number they typed, so show them all to pick from

    # they asked for a big card (jumbo, oversized...)
    if found.get('size') == 'Jumbo':
        big = [p for p in matching if p['size'] != 'Standard']
        if big:
            matching = big
        # TODO (Pokémon): the Pokémon API doesn't list jumbo cards, so pre-pick Modern Jumbo
        # (2020 and later) or Vintage Jumbo (before 2020) for the user here
        # Magic: Scryfall knows every oversized card, so if there's none, show the normal ones
        # (the search page says there's no oversized version). sports cards are always Standard

    for p in matching:
        p['category'] = found['category']
        p['subcategory'] = found.get('subcategory') if found['category'] == 'Sports' else None
    return matching[:MAX_RESULTS], len(matching)


def enrich(found):
    """The single best printing for a card (used for poll cards)."""
    printings, total = find_printings(found)
    if printings:
        return printings[0]
    return None