from flask import Flask, jsonify, request
from datetime import datetime

app = Flask(__name__)

current = None
waiting = []
missed = []
next_no = 1
PRINTER_IP = "192.168.0.151"
PRINTER_PORT = 9100


@app.route("/print", methods=["POST"])
def print_api():
    data = request.get_json()

    ticket_number = data.get("ticketNumber")
    service = data.get("service", "一般服務")
    timestamp = data.get("timestamp") or datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    if not ticket_number:
        return jsonify({"error": "ticketNumber is required"}), 400

    Thread(target=print_ticket, args=(ticket_number, service, timestamp)).start()
    return jsonify({"status": "ok"}), 200


@app.route("/")
def html():
    return open("index.html").read()


@app.route('/status')
def status():
    return jsonify({
        "current": current,
        "waiting": waiting,
        "missed": missed
    })

@app.route('/take', methods=['POST'])
def take():
    global next_no
    waiting.append(next_no)
    next_no += 1
    return '', 204

@app.route('/missed/<int:number>', methods=['DELETE'])
def delete_missed(number):
    global missed
    if number in missed:
        missed.remove(number)
        return '', 204
    else:
        return jsonify({"error": "not found"}), 404

@app.route('/next', methods=['POST'])
def next_call():
    global current
    if waiting:
        current = waiting.pop(0)
    else:
        current = None
    return '', 204

@app.route('/miss', methods=['POST'])
def mark_missed():
    global current
    if current:
        missed.append(current)
        current = None
        next_call()
    return '', 204

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5688)
