from flask import Flask, render_template

app = Flask(__name__)

@app.route("/panel")
def panel():
    return render_template('panel.html', name='Javier')

@app.route("/form")
def form():
    return render_template('form.html')

