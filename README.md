# TopDeck Card Rater

Search for trading cards, from Magic and Pokémon to baseball and more, add them to the deck, rate your favorites, and vote in community polls.

CSI 3210 Final Project, Fall 2026

## Features

- **Search and browse** cards by category (Magic, Pokémon, Sports, Other) and by sport
- **AI search:** describe what you want ("best 80s basketball rookies") and Claude finds real cards
- **Add to the deck:** the deck starts empty and grows as users add cards
- **Rate** cards 1–5 stars and see the community average
- **Vote** in themed polls like "Best Fire-type Pokémon card?"
- **TopDeck Insight:** a short AI-written note on why a card matters
- **Sign-in pop-up** that returns you to the page you were on

## Tech Stack

| Layer | Tools |
|------|------|
| Backend | Python, Flask |
| Frontend | HTML, CSS, Jinja2 templates |
| Database | SQLite |
| Analytics | PostHog |
| AI | Claude API (claude-haiku-5-5) |
| Card images | Scryfall (Magic), TCGdex (Pokémon) |

## Running the App

1. Clone the repo and open the project folder:
```
   git clone https://github.com/nkapanowski/CSI3210project.git
   cd CSI3210project
```
2. Install the packages:
```
   python -m pip install -r requirements.txt
```
3. Copy `config.example.py` to `config.py` and fill in your PostHog key, Anthropic key, and a secret key. `config.py` is in `.gitignore`, so never commit it.
```
   cp config.example.py config.py
```
4. Build the database (this also creates the polls):
```
   python init_db.py
```
5. Start the app and open http://127.0.0.1:5000:
```
   python app.py
```

Running `init_db.py` again resets the database and erases all cards, ratings, and votes.

## Project Structure

```
app.py          starts the app and connects the routes
routes/         pages, card, polls, and sign-in routes
templates/      HTML pages (all extend global.html)
static/         CSS files
db.py           database queries
schema.sql      database tables
init_db.py      builds topdeck.db
insights.py     Claude AI search and TopDeck Insight
sources.py      card image lookups
helpers.py      PostHog tracking and sign-in helpers
```

## Team

| Name | Role |
| Zachary Simon | QA tester & Researcher |
| Alec Kubs | Developer |
| Natalie Kapanowski | Lead Developer |
| Austin Malega | Innovation & UX Strategist |
