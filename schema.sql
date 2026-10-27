-- database tables (SQLite)

DROP TABLE IF EXISTS poll_votes;
DROP TABLE IF EXISTS poll_options;
DROP TABLE IF EXISTS polls;
DROP TABLE IF EXISTS ratings;
DROP TABLE IF EXISTS cards;
DROP TABLE IF EXISTS users;

CREATE TABLE users (
    username   TEXT PRIMARY KEY,
    email      TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE cards (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    category    TEXT NOT NULL CHECK (category IN ('Magic', 'Pokémon', 'Sports', 'Other')),
    subcategory TEXT,                       -- the sport, for Sports cards
    set_or_year TEXT,
    image_url   TEXT,
    source      TEXT DEFAULT 'user',        -- starter, user, ai, scryfall, tcgdex
    external_id TEXT,                       -- the card's ID on Scryfall/TCGdex
    in_deck     INTEGER DEFAULT 1,          -- 0 = only used in a poll, not added to deck yet
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE ratings (
    username   TEXT NOT NULL,
    card_id    INTEGER NOT NULL REFERENCES cards(id),
    stars      INTEGER NOT NULL CHECK (stars BETWEEN 1 AND 5),
    rated_at   TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (username, card_id)         -- one rating per user per card
);

CREATE TABLE polls (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    question TEXT NOT NULL,
    active   INTEGER DEFAULT 1
);

CREATE TABLE poll_options (
    poll_id INTEGER NOT NULL REFERENCES polls(id),
    card_id INTEGER NOT NULL REFERENCES cards(id),
    PRIMARY KEY (poll_id, card_id)
);

CREATE TABLE poll_votes (
    poll_id  INTEGER NOT NULL REFERENCES polls(id),
    username TEXT NOT NULL,
    card_id  INTEGER NOT NULL REFERENCES cards(id),
    PRIMARY KEY (poll_id, username)         -- one vote per user per poll
);