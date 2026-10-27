# database functions 
# run "python init_db.py" once to create topdeck.db
# to reset datatbase, delete topdeck.db and run "python init_db.py" again

import os
import sqlite3

# path to topdeck.db
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'topdeck.db')

# category choices, and the subcategories for Sports
CATEGORIES = ['Magic', 'Pokémon', 'Sports', 'Other']
SPORTS = ['Baseball', 'Basketball', 'Football', 'Hockey', 'Soccer']

# every card query starts with this to get avg rating and count
CARD_SELECT = '''
    SELECT cards.*, ROUND(AVG(ratings.stars), 1) AS avg_rating, COUNT(ratings.stars) AS rating_count
    FROM cards LEFT JOIN ratings ON ratings.card_id = cards.id
'''


###---- helpers ----###

def query_all(sql, params=()):
    """Runs a SELECT and returns a list of rows (each row is a dict)."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # lets us read columns by name in sql db, like row['name']
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def query_one(sql, params=()):
    """Runs a SELECT and returns the first row, or None if there isn't one."""
    rows = query_all(sql, params)
    if rows:
        return rows[0]
    return None


def execute(sql, params=()):
    """Runs an INSERT/UPDATE/DELETE, saves it, and returns the new row's id."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute(sql, params)
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return new_id


###---- users ----###

def get_or_create_user(username, email):
    """Saves the user, or updates their email if they exist."""
    execute('INSERT OR REPLACE INTO users (username, email) VALUES (?, ?)', (username, email))


###---- cards ----##
# a card is "in the deck" once a user physically adds it
# poll cards are saved so the polls work, and the user has cards to vote on before adding any to their deck
# but they stay out of the deck (in_deck = 0) until someone adds them

def get_cards(category=None, subcategory=None, search=None):
    """Cards in the deck, optionally filtered. This is what Browse shows."""
    sql = CARD_SELECT + ' WHERE cards.in_deck = 1'
    params = []
    if category:
        sql += ' AND cards.category = ?'
        params.append(category)
    if subcategory:
        sql += ' AND cards.subcategory = ?'
        params.append(subcategory)
    if search:
        sql += ' AND cards.name LIKE ?'
        params.append('%' + search + '%')
    sql += ' GROUP BY cards.id ORDER BY rating_count DESC, cards.name'
    return query_all(sql, params)


def get_card(card_id):
    """One card by id, or None."""
    return query_one(CARD_SELECT + ' WHERE cards.id = ? GROUP BY cards.id', (card_id,))


def add_card(name, category, subcategory, set_or_year, image_url=None, source='user',
             external_id=None, in_deck=True):
    """Saves a new card and returns its id."""
    if in_deck:
        in_deck_value = 1
    else:
        in_deck_value = 0
    return execute('INSERT INTO cards (name, category, subcategory, set_or_year, image_url, source, external_id, in_deck) '
                   'VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                   (name, category, subcategory, set_or_year, image_url, source, external_id, in_deck_value))


def find_saved_card(name, category, external_id=None):
    """Looks for a card we've already saved: first by its API id, then by name. Returns the row or None."""
    if external_id:
        card = query_one('SELECT * FROM cards WHERE external_id = ?', (external_id,))
        if card:
            return card
    return query_one('SELECT * FROM cards WHERE LOWER(name) = LOWER(?) AND category = ?', (name, category))


def find_card(name, category, external_id=None):
    """Returns the id of a matching card that's in the deck, or None. Doesn't add anything."""
    card = find_saved_card(name, category, external_id)
    if card and card['in_deck']:
        return card['id']
    return None


def find_or_add_card(name, category, subcategory, set_or_year, image_url=None, source='ai',
                     external_id=None, in_deck=True):
    """Returns the card's id, saving it first if it's new.
    in_deck=False is for poll cards: saved, but not added to the deck."""
    card = find_saved_card(name, category, external_id)
    if card is None:
        return add_card(name, category, subcategory, set_or_year, image_url, source, external_id, in_deck)

    # We already have it. Fill in a picture if it didn't have one, and add it to the deck if asked.
    if image_url and not card['image_url']:
        execute('UPDATE cards SET image_url = ?, external_id = ? WHERE id = ?',
                (image_url, external_id, card['id']))
    if in_deck and not card['in_deck']:
        add_to_deck(card['id'])
    return card['id']


def add_to_deck(card_id):
    """Puts a saved card in the deck (shows in Browse)."""
    execute('UPDATE cards SET in_deck = 1 WHERE id = ?', (card_id,))


###---- ratings -----###

def get_user_rating(username, card_id):
    """The user's stars for this card, or None."""
    row = query_one('SELECT stars FROM ratings WHERE username = ? AND card_id = ?', (username, card_id))
    if row:
        return row['stars']
    return None


def add_rating(username, card_id, stars):
    # one rating per user per card, rating again replaces the old one
    execute('INSERT OR REPLACE INTO ratings (username, card_id, stars) VALUES (?, ?, ?)',
            (username, card_id, stars))


###---- polls -----###

def create_poll(question, card_ids):
    """Saves a poll and its choices, returns the poll id."""
    poll_id = execute('INSERT INTO polls (question) VALUES (?)', (question,))
    # OR IGNORE skips duplicate cards
    for card_id in card_ids:
        execute('INSERT OR IGNORE INTO poll_options (poll_id, card_id) VALUES (?, ?)', (poll_id, card_id))
    return poll_id


def get_polls():
    """Every active poll, with each choice's card, vote count, and percentage."""
    polls = []
    for poll in query_all('SELECT * FROM polls WHERE active = 1 ORDER BY id'):
        rows = query_all('SELECT poll_options.card_id, COUNT(poll_votes.username) AS votes '
                         'FROM poll_options LEFT JOIN poll_votes '
                         'ON poll_votes.poll_id = poll_options.poll_id AND poll_votes.card_id = poll_options.card_id '
                         'WHERE poll_options.poll_id = ? GROUP BY poll_options.card_id ORDER BY poll_options.rowid',
                         (poll['id'],))

    # total votes, used for percents
        total = 0
        for row in rows:
            total += row['votes']

        options = []
        for row in rows:
            percent = 0
            if total > 0:
                percent = round(row['votes'] / total * 100)
            options.append({'card': get_card(row['card_id']), 'votes': row['votes'], 'percent': percent})

        polls.append({'id': poll['id'], 'question': poll['question'], 'options': options, 'total': total})
    return polls


def get_user_votes(username):
    """Which card the user picked in each poll, like {1: 5} meaning poll 1 -> card 5."""
    votes = {}
    for row in query_all('SELECT poll_id, card_id FROM poll_votes WHERE username = ?', (username,)):
        votes[row['poll_id']] = row['card_id']
    return votes


def add_vote(username, poll_id, card_id):
    """Saves a vote. Returns False if that card isn't one of the poll's choices."""
    choice = query_one('SELECT * FROM poll_options WHERE poll_id = ? AND card_id = ?', (poll_id, card_id))
    if choice is None:
        return False
    # one vote per user per poll, voting again replaces old one
    execute('INSERT OR REPLACE INTO poll_votes (poll_id, username, card_id) VALUES (?, ?, ?)',
            (poll_id, username, card_id))
    return True