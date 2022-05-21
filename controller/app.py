import numpy as np
from flask import Flask, send_from_directory
from flask_restful import Api, Resource, reqparse
from flask_cors import CORS # disable on deployment
# from api.HelloApiHandler import HelloApiHandler
import sse

from flask import Flask, request
from gevent.pywsgi import WSGIServer
import gevent


app = Flask(__name__)
CORS(app)
channel = sse.Channel()

def long_repeating_task():
	i = 0
	while True:
		x = np.arange(16)
		y = np.sin(i + x)
		channel.publish({
			"x": x.tolist(),
			"y": y.tolist(),
		})
		i += 1
		gevent.sleep(0.1)

t = gevent.spawn(long_repeating_task)

@app.route("/subscribe")
def subscribe():
	return channel.subscribe()

@app.route("/publish", methods=["POST"])
def publish():
	channel.publish(request.data)
	return "OK"

@app.route("/")
def index():
	return """<body><script>
var eventSource = new EventSource('/subscribe');
eventSource.onmessage = function(m) {
	console.log(m);
	var el = document.getElementById('messages');
	el.innerHTML += m.data;
	el.innerHTML += '</br>';
}
function post(url, data) {
	var request = new XMLHttpRequest();
	request.open('POST', url, true);
	request.setRequestHeader('Content-Type', 'text/plain; charset=UTF-8');
	request.send(data);
}
function publish() {
	var message = document.getElementById('msg').value;
	post('/publish', message);
}
</script>
<input type='text' id='msg'>
<button onclick='publish()'>send</button>
<p id='messages'></p>
</body>"""

def main():
	port = 5000
	server = WSGIServer(("", port), app)
	print(f"Listening on port: {port}")
	server.serve_forever()

if __name__ == "__main__":
	main()

# app = Flask(__name__, static_url_path="", static_folder="frontend/build")
# CORS(app) # disable on deployment
# api = Api(app)

# channel = sse.Channel()

# @app.route("/", defaults={"path": ""})
# def serve(path):
#     return send_from_directory(app.static_folder, "index.html")

# api.add_resource(HelloApiHandler, "/flask/hello")

# @app.route('/subscribe')
# def subscribe():
#     return channel.subscribe()

# @app.route('/publish')
# def publish():
#     channel.publish('message here')
#     return "OK"