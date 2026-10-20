# claude features: find_cards(): turns a search into real cards
# generate_insight(): short text on why a card matters
# uses ANTHROPIC_API_KEY from config.py (never commit)

import anthropic

import config

MODEL = 'claude-haiku-5-5'   # small, fast, cheap 

client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

def ask_claude(system, user_text, max_tokens):
    """Sends one message to Claude and returns its text reply."""
    response = client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{'role': 'user', 'content': user_text}],
    )
    text = ''
    for block in response.content:
        if block.type == 'text':
            text += block.text
    text = text.strip()

    # if claude ran out of room before writing anything, treat it as an error
    # (instead of saving a blank answer) so the page shows "Try again"
    if not text:
        raise RuntimeError('Claude sent back no text (stop reason: ' + str(response.stop_reason) + ')')
    return text

###---- AI search bar ----###

FIND_PROMPT = (
    "You help users find real trading cards on TopDeck. Given a search, list the real cards the user "
    "most likely means, best match first, at most 6. Only list cards you are confident actually exist. "
    "Use the card's exact official name (for Magic and Pokémon, the name printed on the card). "
    "Yu-Gi-Oh! and other card games go in the Other category. "
    "If the search is not about trading cards, return an empty list. Always answer with the show_cards tool."
)

# allowed values, anything else gets cleaned up below
VALID_CATEGORIES = ['Magic', 'Pokémon', 'Sports', 'Other']
VALID_SPORTS = ['Baseball', 'Basketball', 'Football', 'Hockey', 'Soccer']

# claude fills in this structure instead of free text, so the data is always clean
SHOW_CARDS_TOOL = {
    'name': 'show_cards',
    'description': 'Show the user the trading cards that match their search.',
    'input_schema': {
        'type': 'object',
        'properties': {
            'cards': {
                'type': 'array',
                'maxItems': 6,
                'items': {
                    'type': 'object',
                    'properties': {
                        'name': {'type': 'string', 'description': 'Official card name'},
                        'category': {'type': 'string', 'enum': VALID_CATEGORIES},
                        'subcategory': {'type': 'string', 'enum': VALID_SPORTS,
                                        'description': 'The sport. Only for Sports cards.'},
                        'set_or_year': {'type': 'string', 'description': "Set and year, like 'Topps (1952)'"},
                        'reason': {'type': 'string', 'description': 'Why it matches, under 12 words'},
                    },
                    'required': ['name', 'category', 'set_or_year', 'reason'],
                },
            },
        },
        'required': ['cards'],
    },
}


def find_cards(query):
    """Asks Claude which real cards match a search. Returns card dicts (not saved)."""
    response = client.messages.create(
        model=MODEL,
        max_tokens=1000,
        system=FIND_PROMPT,
        tools=[SHOW_CARDS_TOOL],
        tool_choice={'type': 'tool', 'name': 'show_cards'},  # must answer with the tool
        messages=[{'role': 'user', 'content': 'Search: ' + query}],
    )
    # the answer is the tool's input: {'cards': [...]}
    cards = []
    for block in response.content:
        if block.type == 'tool_use':
            cards = block.input.get('cards', [])

    # clean up each card so the values are valid
    cleaned = []
    for c in cards:
        name = (c.get('name') or '').strip()
        if not name:
            continue
        category = c.get('category')
        if category not in VALID_CATEGORIES:
            category = 'Other'
        subcategory = c.get('subcategory')
        if category != 'Sports' or subcategory not in VALID_SPORTS:
            subcategory = None
        cleaned.append({
            'name': name,
            'category': category,
            'subcategory': subcategory,
            'set_or_year': (c.get('set_or_year') or '').strip(),
            'reason': (c.get('reason') or '').strip(),
        })
    return cleaned[:6]

###---- topdeck insight via claude ----###

INSIGHT_PROMPT = (
    "You are TopDeck's card expert. In 2-3 friendly sentences, explain why this trading card "
    "is notable to collectors or players: its history, rarity, or what makes it iconic. "
    "Do not give prices or investment advice. If you don't recognize the card, say so briefly "
    "and describe what makes cards from that set or year interesting instead."
)

# insights by card id, kept in memory (reset when the app restarts)

saved_insights = {}

 
def get_insight(card_id):
    return saved_insights.get(card_id)
 
 
def generate_insight(card):
    """Asks Claude about the card (only once per card). Returns (text, was_new)."""
    if card['id'] in saved_insights:
        return saved_insights[card['id']], False
 
    details = ('Card: ' + card['name'] + '\n'
               + 'Category: ' + (card['subcategory'] or card['category']) + '\n'
               + 'Set/year: ' + (card['set_or_year'] or ''))
    text = ask_claude(INSIGHT_PROMPT, details, max_tokens=1024)  # room to think + a 2-3 sentence answer
    saved_insights[card['id']] = text
    return text, True