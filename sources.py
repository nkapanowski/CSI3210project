# real card details and images from free APIs (no keys needed)
# Scryfall for Magic  (https://scryfall.com/docs/api)
# TCGdex for Pokémon   (https://tcgdex.dev)
# sports cards have no free API, so they use claude's details (no images)

import requests

# sent with every request so the APIs know who's asking
HEADERS = {'User-Agent': 'TopDeck/1.0 (CSI 3210 class project)', 'Accept': 'application/json'}
TIMEOUT = 6  # seconds, so a slow API doesn't freeze the page


def lookup_magic(name):
    """Finds a Magic card by name on Scryfall. Returns a dict or None."""
    r = requests.get('https://api.scryfall.com/cards/named', params={'fuzzy': name},
                     headers=HEADERS, timeout=TIMEOUT)
    if r.status_code != 200:
        return None
    card = r.json()

    # double-sided cards keep the picture on the first face
    images = card.get('image_uris')
    if not images and card.get('card_faces'):
        images = card['card_faces'][0].get('image_uris')
    image_url = None
    if images:
        image_url = images.get('normal')

    # ex. 'Alpha (1993)'
    set_or_year = card.get('set_name', '')
    year = (card.get('released_at') or '')[:4]
    if year:
        set_or_year = set_or_year + ' (' + year + ')'

    return {
        'name': card['name'],
        'set_or_year': set_or_year,
        'image_url': image_url,
        'source': 'scryfall',
        'external_id': card['id'],
    }


def lookup_pokemon(name):
    """Finds a Pokémon card by name on TCGdex. Returns a dict or None."""
    r = requests.get('https://api.tcgdex.net/v2/en/cards', params={'name': name},
                     headers=HEADERS, timeout=TIMEOUT)
    if r.status_code != 200 or not r.json():
        return None
    results = r.json()

    # best match: exact name with a picture, else any with a picture, else the first
    best = results[0]
    for c in results:
        if c.get('image'):
            best = c
            break
    for c in results:
        if c.get('name', '').lower() == name.lower() and c.get('image'):
            best = c
            break

    # second request to get the set name
    set_name = ''
    detail = requests.get('https://api.tcgdex.net/v2/en/cards/' + best['id'], headers=HEADERS, timeout=TIMEOUT)
    if detail.status_code == 200:
        card_set = detail.json().get('set')
        if card_set:
            set_name = card_set.get('name', '')

    image_url = None
    if best.get('image'):
        image_url = best['image'] + '/high.webp'

    return {
        'name': best['name'],
        'set_or_year': set_name,
        'image_url': image_url,
        'source': 'tcgdex',
        'external_id': best['id'],
    }


def enrich(card):
    """Swaps Claude's card details for real API data when found."""
    try:
        if card['category'] == 'Magic':
            found = lookup_magic(card['name'])
        elif card['category'] == 'Pokémon':
            found = lookup_pokemon(card['name'])
        else:
            found = None
    except requests.RequestException:
        found = None  # API down or slow, use claude's details

    card = dict(card)  # copy so claude's original isn't changed
    if found:
        card.update(found)  # real name, set, picture, and id
    else:
        card['image_url'] = None
        card['source'] = 'ai'
        card['external_id'] = None
    return card