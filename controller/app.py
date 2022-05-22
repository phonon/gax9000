import numpy as np
import os
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

def run(
    port=9000,
    data_path="./data",
):
    print(f"Data path: \"{data_path}\"")
    # create data folder if does not exist
    if not os.path.exists(data_path):
        import shutil
        shutil.copytree(
            src=os.path.join("controller", "assets"),
            dst=data_path,
        )
        print(f"Generating new default config in data path: \"{data_path}\"")

    
    # run server
    server = WSGIServer(("", port), app)
    print(f"Listening on port: {port}")
    server.serve_forever()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run training on neural net model")

    parser.add_argument(
        "data_path",
        metavar="data_path",
        type=str,
        help="Controller config data path"
    )
    parser.add_argument(
        "--port",
        dest="port",
        metavar="port",
        type=int,
        default=9000,
        help="Controller config data path"
    )

    args = vars(parser.parse_args())

    run(**args)
