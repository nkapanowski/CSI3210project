# home page and browse/search.

from flask import Blueprint, render_template, request, redirect, url_for, session

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
    size = request.args.get('size')
    if size not in db.sizes_for(category):
        size = None  # also clears a size that doesn't fit this category (like Oversized on Pokémon)

    cards = db.get_cards(category, subcategory, search, size)
    suggestions = []    # cards Claude found that aren't in the deck yet
    notes = []          # like "No oversized Black Lotus, showing regular printings"
    used_ai = False
    ai_failed = False
    found_categories = {c['category'] for c in cards}  # which games are in the results

    # ask Claude which cards the user means, so they see every printing (other sets, sizes),
    # not just the ones already in the deck
    if search:
        try:
            ai_cards, suggestions, notes = ai_search(search)
            used_ai = True
            found_categories |= {c['category'] for c in ai_cards + suggestions}
            # deck cards that matched by name come first, then the ones Claude found
            shown = [c['id'] for c in cards]
            for c in ai_cards:
                if c['id'] not in shown and (not size or c['size'] == size):
                    cards.append(c)
                    shown.append(c['id'])
            if size:
                suggestions = [s for s in suggestions if s['size'] == size]
        except Exception as error:  # bad API key, no credits, no internet, etc.
            print('AI search failed:', error)
            ai_failed = True

    if search:
        track('card_searched', query=search, results=len(cards),
              suggestions=len(suggestions), smart_search=used_ai)
    else:
        track('page_view', page='browse', category=category, subcategory=subcategory)

    # remember this page, so a card's "← Back" link returns here (search, filters and all)
    if search:
        back_label = f'results for "{search}"'
    else:
        back_label = subcategory or category or 'Browse'
    session['back_to'] = [request.full_path, back_label]

    # size filter: only the sizes that fit. with a category picked, that category's sizes.
    # searching "All", the sizes of the games in the results (Black Lotus -> Standard, Oversized)
    sizes = db.sizes_for(category)
    if not category and found_categories:
        sizes = [s for s in db.SIZES
                 if s == size or any(s in db.sizes_for(c) for c in found_categories)]

    return render_template('browse.html', cards=cards, suggestions=suggestions, notes=notes,
                           category=category, subcategory=subcategory, search=search, size=size,
                           categories=db.CATEGORIES, sports=db.SPORTS, sizes=sizes,
                           sizes_by_category=db.SIZES_BY_CATEGORY,
                           used_ai=used_ai, ai_failed=ai_failed,
                           reported=request.args.get('reported'))


def ai_search(search):
    """Asks Claude which cards the user means, then gets each card's real printings.
    Returns (cards already in the deck, new cards to suggest, notes for the page).
    Nothing is saved here. New cards are only saved when the user clicks Add to TopDeck."""
    in_deck = []
    new_cards = []
    seen = []          # (card id or name, size) so the same printing isn't shown twice
    looked_up = []     # card names already looked up, in case Claude lists one twice
    notes = []

    for found in insights.find_cards(search):
        name_key = (found['name'].lower(), found['category'])
        if name_key in looked_up:
            continue
        looked_up.append(name_key)

        printings, total = sources.find_printings(found)  # real sets, numbers, and pictures

        # asked for a big Magic card but there isn't one
        if found.get('size') == 'Jumbo' and found['category'] == 'Magic' and printings \
                and all(p['size'] == 'Standard' for p in printings):
            notes.append(f'There\'s no oversized {found["name"]}, so these are its regular printings.')

        for card in printings:
            key = (card['external_id'] or card['name'], card['size'])
            if key in seen:
                continue
            seen.append(key)
            card['reason'] = found['reason']

            card_id = db.find_card(card['name'], card['category'], card['external_id'], card['size'])
            if card_id:
                deck_card = db.get_card(card_id)
                deck_card['reason'] = found['reason']
                in_deck.append(deck_card)
            else:
                new_cards.append(card)

    return in_deck, new_cards, notes


@pages.route('/search/wrong', methods=['POST'])
def wrong_result():
    """"Not what I meant" button on an AI search result. Claude reads this next time."""
    search = request.form.get('search', '')
    card_text = request.form.get('name', '') + ' (' + request.form.get('set_or_year', '') + ')'
    insights.save_note(search, card_text, right=False)
    track('search_result_wrong', query=search, card_name=request.form.get('name'))
    return redirect(url_for('pages.browse', q=search, reported=1))