# home page and browse/search.

from flask import Blueprint, render_template, request

import db
import insights
import sources
from helpers import track

pages = Blueprint('pages', __name__)


@pages.route('/')
def home():
    track('page_view', page='home')
    return render_template('home.html', categories=db.CATEGORIES)


@pages.route('/browse')
def browse():
    category = request.args.get('category')
    subcategory = request.args.get('sub')
    search = request.args.get('q', '').strip()

    cards = db.get_cards(category, subcategory, search)
    suggestions = []    # cards Claude found that aren't in the deck yet
    used_ai = False
    ai_failed = False

    # no card names matched, so ask Claude which cards the user means
    if search and not cards:
        try:
            cards, suggestions = ai_search(search)
            used_ai = True
        except Exception as error:  # bad API key, no credits, no internet, etc.
            print('AI search failed:', error)
            ai_failed = True

    if search:
        track('card_searched', query=search, results=len(cards),
              suggestions=len(suggestions), smart_search=used_ai)
    else:
        track('page_view', page='browse', category=category, subcategory=subcategory)

    return render_template('browse.html', cards=cards, suggestions=suggestions,
                           category=category, subcategory=subcategory, search=search,
                           categories=db.CATEGORIES, sports=db.SPORTS,
                           used_ai=used_ai, ai_failed=ai_failed)


def ai_search(search):
    """Asks Claude for matching cards. Returns (cards already in the deck, new cards to suggest).
    Nothing is saved here. New cards are only saved when the user clicks Add to TopDeck."""
    in_deck = []
    new_cards = []
    new_names = []

    for found in insights.find_cards(search):
        card = sources.enrich(found)  # adds the real picture for Magic and Pokémon
        card['reason'] = found['reason']
        card_id = db.find_card(card['name'], card['category'], card['external_id'])

        if card_id:
            deck_card = db.get_card(card_id)
            deck_card['reason'] = found['reason']
            in_deck.append(deck_card)
        elif card['name'] not in new_names:
            new_cards.append(card)
            new_names.append(card['name'])

    return in_deck, new_cards