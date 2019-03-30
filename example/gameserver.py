#!/usr/bin/env python

from flask import Flask, jsonify, request, abort

app = Flask(__name__)

CREDENTIALS = {
    'markku': '3l1t3',
    'guest':  'lam3'
}

@app.route('/game/login')
def index():
    user = request.args['user'] if 'user' in request.args else ''
    passw = request.args['pass'] if 'pass' in request.args else ''

    if user in CREDENTIALS:
        exp_pass = CREDENTIALS[user]
        if passw == exp_pass:
            return jsonify({'status': 'OK'})

    abort(401)

if __name__ == '__main__':
    app.run(debug=True)
