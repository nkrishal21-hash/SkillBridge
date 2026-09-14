"""
run.py — SkillBridge application entry point.
Usage:
    Development : python run.py
    Production  : gunicorn -k geventwebsocket.gunicorn.workers.GeventWebSocketWorker \
                           -w 1 "run:create_app()"
"""

from app import create_app, socketio

app = create_app()

if __name__ == "__main__":
    # eventlet/gevent not required for dev; threading mode handles SocketIO
    socketio.run(
        app,
        host="0.0.0.0",
        port=5001,
        debug=app.config["DEBUG"],
        use_reloader=True,
        log_output=True,
        allow_unsafe_werkzeug=True,   # required by Flask-SocketIO >= 5.x in dev
    )
