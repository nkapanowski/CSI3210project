import atexit
from flask import Flask, render_template
from posthog import Posthog
import config

app = Flask(__name__)
app.secret_key = config.SECRET_KEY

posthog = Posthog(config.POSTHOG_API_KEY, host=config.POSTHOG_HOST)
atexit.register(posthog.shutdown)

@app.route("/")
def home():
    posthog.capture('page_view', distinct_id='test_user', properties={'page':'home'})
    return render_template('home.html')

if __name__ == "__main__":
    app.run(debug=True)