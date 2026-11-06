# real card details and images from free APIs (no keys needed)
# Scryfall for Magic  (https://scryfall.com/docs/api)
# TCGdex for Pokémon   (https://tcgdex.dev)
# sports cards have no free API, so they use claude's details (no images)

# one card name (like "Charizard") has many printings: different sets, numbers, and sizes.
# find_printings() gets the real printings from the API and keeps the ones that match
# what the user asked for (set, year, card number, size).

import re

import requests

# sent with every request so the APIs know who's asking
HEADERS = {'User-Agent': 'TopDeck/1.0 (CSI 3210 class project)', 'Accept': 'application/json'}
TIMEOUT = 6          # seconds, so a slow API doesn't freeze the page
MAX_RESULTS = 250    # safety limit so one search can't load thousands of pictures


###---- magic (Scryfall) ----###

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
    image_url = None
    if images:
        image_url = images.get('normal')

    set_name = card.get('set_name', '')
    year = (card.get('released_at') or '')[:4]
    number = card.get('collector_number', '')

    # scryfall marks big display cards (like oversized Commander cards) as "oversized"
    size = 'Standard'
    if card.get('oversized'):
        size = 'Jumbo'

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
    params = {'q': '!"' + name + '"', 'unique': 'prints', 'order': 'released', 'dir': 'desc'}
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
    return [magic_card(card) for card in r.json().get('data', [])]


###---- pokémon (TCGdex) ----###

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
            'size': 'Standard',  # TCGdex doesn't list jumbo cards, users pick the size when adding
            'image_url': image_url,
            'back_image_url': None,
            'source': 'tcgdex',
            'external_id': c['id'],
        })

    # cards with a picture first
    printings.sort(key=lambda p: p['image_url'] is None)
    return printings


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
    details = [['Type', card.get('type_line') or face.get('type_line')],
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
    try:
        if card.get('source') == 'scryfall' and card.get('external_id'):
            return magic_details(card['external_id'])
        if card.get('source') == 'tcgdex' and card.get('external_id'):
            return pokemon_details(card['external_id'])
    except requests.RequestException:
        return []  # API down or slow, save the card without details

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
        else:
            printings = None  # no free API for sports and other cards
    except requests.RequestException:
        printings = None  # API down or slow

    # no API to check with: use Claude's details
    if printings is None:
        card = dict(found)
        card.update({'image_url': None, 'back_image_url': None, 'source': 'ai', 'external_id': None,
                     'size': 'Jumbo' if found.get('size') == 'Jumbo' else 'Standard'})
        return [card], 1

    # the API has no card with this name, so Claude probably got it wrong: skip it
    if not printings:
        return [], 0

    matching = [p for p in printings if matches(p, found)]
    if not matching:
        matching = printings  # nothing fit the set/number they typed, so show them all to pick from

    # they asked for a jumbo card
    if found.get('size') == 'Jumbo':
        jumbo = [p for p in matching if p['size'] != 'Standard']
        if jumbo:
            matching = jumbo
        else:
            for p in matching:  # the API doesn't list jumbos, so pre-pick Jumbo for the user
                p['size'] = 'Jumbo'

    for p in matching:
        p['category'] = found['category']
        p['subcategory'] = None
    return matching[:MAX_RESULTS], len(matching)


def enrich(found):
    """The single best printing for a card (used for poll cards)."""
    printings, total = find_printings(found)
    if printings:
        return printings[0]
    return None