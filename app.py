# Flask starts the app
# pages live in the routes/ folder: auth, card, pages, polls

import os

from flask import Flask, session

import config
import db
from routes.auth import auth
from routes.card import cards
from routes.pages import pages
from routes.polls import polls

if not os.path.exists(db.DB_PATH):
    print('No database yet. Run "python init_db.py" first, then "python app.py".')
    exit()

app = Flask(__name__)
app.secret_key = config.SECRET_KEY

# plugs each group of pages from routes/ into app so the URLs work
app.register_blueprint(pages)
app.register_blueprint(cards)
app.register_blueprint(polls)
app.register_blueprint(auth)


# all templates use current_user for "Hi, name" in the menu
# if a user is not signed in, current_user will be None
@app.context_processor
def add_current_user():
    return {'current_user': session.get('username')}


if __name__ == '__main__':
    app.run(debug=True)