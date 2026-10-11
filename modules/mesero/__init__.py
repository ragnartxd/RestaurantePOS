"""
Package for the waitstaff order web server (phone, local WiFi).

Usage:
    from modules.mesero import FlaskServer

    server = FlaskServer(db, callback_comanda=my_function)
    server.iniciar()
    ...
    server.detener()

Internal structure:
    constantes.py      -> PIN, port, variant groups
    plantilla_html.py  -> HTML/CSS served at "/"
    static/app.js      -> the app's JavaScript (served at /static/app.js)
    rutas.py           -> FlaskServer class and the endpoints (/api/...)
"""

from .rutas import FlaskServer

__all__ = ["FlaskServer"]