# builds topdeck.db from schema.sql and creates polls
# run "python init_db.py" once to create topdeck.db
# to reset datatbase, delete topdeck.db and run "python init_db.py" again

# no starter cards, cards come in through search
# Claude picks poll cards, they're saved but not added to the deck

import os
import sqlite3

import db
import insights
import sources

# edit these to change the polls
POLL_QUESTIONS = [
    'Best Fire-type Pokémon card?',
    'Most iconic Magic: The Gathering card?',
    'Greatest basketball rookie card?',
    'Best Water-type Pokémon card?',
]
CARDS_PER_POLL = 4


def build_tables():
    """Creates the tables from schema.sql."""
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, 'schema.sql'), encoding='utf-8') as f:
        schema = f.read()
    conn = sqlite3.connect(db.DB_PATH)
    conn.executescript(schema)
    conn.commit()
    conn.close()


def build_poll(question):
    """Asks Claude for cards, saves them, and creates the poll."""
    card_ids = []
    # extra rules so the choices fit the question and don't repeat
    request = (f"{question} Pick {CARDS_PER_POLL} cards for a community poll. Every card must clearly fit "
               "the question (for example, only Fire-type Pokémon for a Fire question). Each card must be a "
               "different character or player: no repeats and no variants of the same one (not Charizard, "
               "Charizard ex, and Charizard VMAX together).")
    for found in insights.find_cards(request):
        card = sources.enrich(found)  # adds real details and picture(for Magic & Pokémon only)
        card_id = db.find_or_add_card(card['name'], card['category'], card['subcategory'],
                                      card['set_or_year'], card['image_url'],
                                      card['source'], card['external_id'], in_deck=False)
        if card_id not in card_ids:
            card_ids.append(card_id)
    # stop once there are enough cards
        if len(card_ids) == CARDS_PER_POLL:
            break
    # a poll needs at least 2 choices
    if len(card_ids) < 2:
        print(f'  Skipped "{question}": not enough cards found.')
        return
    db.create_poll(question, card_ids)
    names = ', '.join(db.get_card(i)['name'] for i in card_ids)
    print(f'  "{question}": {names}')

# terminal output
def main():
    build_tables()
    print(f'Built {db.DB_PATH}')
    print('Creating polls (asks Claude, takes a few seconds each)...')
    for question in POLL_QUESTIONS:
        try:
            build_poll(question)
        except Exception as e:  #bad API key or no internet, skip and keep going
            print(f'  Skipped "{question}": {e}')
    print('Done.')


if __name__ == '__main__':
    main()