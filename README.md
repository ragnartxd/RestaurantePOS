# RestaurantePOS

A desktop **point-of-sale system for restaurants** built with **Python + Tkinter**, with an embedded web server so waitstaff can take orders from their phones over local WiFi, a remote owner dashboard, menu and inventory management, cash-close reports, ESC/POS thermal printing and security-camera viewing.

Everything runs **locally on the restaurant's PC** (no external server or internet connection is needed to operate) and uses SQLite as its database.

> **Status:** designed, built and deployed by me for a real, small restaurant (name withheld). This public repository contains a sanitized copy: no business data, credentials or customer information.

> **License:** source code published for **viewing only** — see [LICENSE](./LICENSE). All rights reserved.

---

## Table of contents

- [Features](#features)
- [Architecture](#architecture)
- [Project structure](#project-structure)
- [Tech stack](#tech-stack)
- [Setup](#setup)
- [Configuration (.env)](#configuration-env)
- [Modules](#modules)
- [Database](#database)
- [License / activation system](#license--activation-system)
- [Networking and ports](#networking-and-ports)
- [Notes about this public version](#notes-about-this-public-version)

---

## Features

- 🧾 **Central register** — Tkinter panel to take orders, charge (cash, transfer or split), edit prices with an audit trail, and print tickets.
- 📱 **Waitstaff app over WiFi** — each waitress opens a URL on her phone (nothing to install), builds the order and sends it straight to the kitchen without going through the register.
- 🖨️ **ESC/POS thermal printing** — print queue with automatic retries for both kitchen orders and register tickets.
- 📊 **Reports and cash close** — daily sales, best-selling products, daily expenses, cash close with calculated difference, Excel export.
- 📦 **Meat inventory** — stock is deducted automatically on payment, with configurable product → supply links.
- 🍽️ **Menu management** — products, categories, quick comments and default included drinks per dish type; editable from the app itself and synced instantly with the waitstaff server.
- 📷 **Security cameras** — tiled view of a HiLook/Hikvision NVR (RTSP), double-click to enlarge any camera.
- 🌐 **Owner's remote dashboard** — separate read-only server with its own password, designed to be exposed to the internet (via Tailscale Funnel) without touching the internal waitstaff network.
- 🔐 **Per-machine activation** — the software is bound to the PC it is installed on through a unique activation key.

## Architecture

```
┌─────────────────────┐        local WiFi        ┌──────────────────────┐
│  Waitstaff app       │ ───────────────────────▶ │  Flask server         │
│ (phone, browser)     │        port 5050          │  modules/mesero/      │
└─────────────────────┘                            └──────────┬───────────┘
                                                              │
┌─────────────────────┐                                       │
│  Central register    │◀──────── SQLite (restaurante.db) ────┤
│  (Tkinter, main.py)  │◀──────── menu.json (MenuStore)  ─────┘
└──────────┬───────────┘
           │
           ├── Thermal printer (ESC/POS) — kitchen and register
           ├── HiLook/Hikvision cameras (RTSP)
           └── Owner dashboard (Flask, port 5051, remote via Tailscale)
```

- The **central register** and the **waitstaff server** are two independent processes on the same PC that share the same SQLite database and the same `menu.json`, so a change made in one is immediately reflected in the other.
- The **owner dashboard** is a third, completely separate Flask server (different port, different password) that is read-only and meant for remote access without exposing the waitstaff system to the internet.

## Project structure

```
├── main.py                       # Entry point: starts the desktop app (Tkinter)
├── data/                         # Persistent data (created at runtime, git-ignored)
│   ├── restaurante.db            #   SQLite database
│   ├── menu.json                 #   Menu shared between register and waitstaff
│   └── .licencia                 #   Saved activation key of the machine
└── modules/
    ├── database.py               # Database class: SQLite access (orders, payments, expenses, inventory…)
    ├── menu_store.py             # Menu persistence in menu.json
    ├── menu_manager.py           # Product/category management UI
    ├── inventario.py             # Meat inventory logic + UI
    ├── reportes.py               # Reports UI, cash close and Excel export
    ├── impresora_cocina.py       # ESC/POS print queue with retries
    ├── licencia.py               # Per-machine activation
    ├── config.py                 # Loads credentials from .env
    ├── rutas_base.py             # Base path resolution (packaged / development)
    ├── camaras.py                # Camera mosaic UI (Tkinter + OpenCV)
    ├── camaras_config.py         # NVR IP/user/password and camera list
    ├── dashboard_server.py       # Owner's remote dashboard (Flask)
    ├── flask_server.py           # Waitstaff Flask server bootstrap
    ├── caja/                     # Register module, split into design and logic
    │   ├── logica.py             #   Pure business rules (included drinks, variants)
    │   ├── dialogos.py           #   Popup windows (payment, split bill, price edit)
    │   └── interfaz.py           #   CajaModule: main register panel (Tkinter)
    └── mesero/                   # Web app for waitstaff
        ├── rutas.py              #   Flask routes + REST API
        ├── constantes.py         #   PIN, port, shared variant groups
        ├── plantilla_html.py     #   Web app HTML
        └── static/app.js         #   Front-end logic
```

## Tech stack

| Area | Technology |
|---|---|
| Desktop UI | Python 3.12+, Tkinter |
| Web servers | Flask (waitstaff app and owner dashboard) |
| Database | SQLite (+ JSON file for the menu) |
| Printing | ESC/POS over network (python-escpos) |
| Cameras | OpenCV (RTSP), Pillow |
| Reports | openpyxl (Excel) |
| Extras | segno (QR codes), PyInstaller-friendly paths |

## Setup

```bash
# 1. Create a virtual environment (recommended)
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # Linux/Mac

# 2. Install dependencies
pip install -r requirements.txt

# 3. Create your .env from the template and edit it
cp .env.example .env

# 4. Run
python main.py
```

> On Linux, if `tkinter` is missing: `sudo apt install python3-tk`

On first launch on a machine, the program asks for an **activation key** (see [License / activation system](#license--activation-system)), creates `data/restaurante.db` and `data/menu.json` with demo data, starts the waitstaff Flask server (port `5050`) and the owner dashboard (port `5051`) in the background, and opens the main register panel.

Waitstaff connect from their phones, on the same WiFi, to `http://<PC-IP>:5050`. The local IP is shown inside the app and can be displayed as a QR code.

## Configuration (.env)

Passwords and sensitive values are **not written in the source code**: they are read from a `.env` file placed next to the `data/` folder (or next to the executable). See [`.env.example`](./.env.example).

| Variable | Used by | Description |
|---|---|---|
| `PIN_ACCESO` | `modules/mesero` | PIN waitstaff enter to access the web app |
| `DASHBOARD_PASSWORD` | `modules/dashboard_server.py` | Password of the owner's read-only remote dashboard |
| `NVR_IP` / `NVR_USUARIO` / `NVR_PASSWORD` | `modules/camaras_config.py` | Camera recorder (NVR) connection |
| `CAMERAS_PASSWORD` | `main.py` | Password that unlocks the Cameras tab |
| `SUPERVISOR_PASSWORD` | `modules/reportes.py` | Authorization to delete an expense |
| `LICENSE_SECRET` | `modules/licencia.py` | Secret used to derive per-machine activation keys |

## Modules

- **`Database`** (`modules/database.py`) — SQLite data layer: orders, order lines, rounds, payments, expenses, cash closes, inventory and its product links, and price-edit history. Tables are created with `CREATE TABLE IF NOT EXISTS` and include soft migrations (`ALTER TABLE`) so no data is lost when upgrading.
- **`MenuStore`** (`modules/menu_store.py`) — the menu lives in `data/menu.json`, not in SQLite. Both the register and the waitstaff server read and write the same file, so a price change made at the register shows up instantly on the waitresses' phones.
- **`caja/`** — split into `logica.py` (pure business rules, no UI dependency), `dialogos.py` (Tkinter popups) and `interfaz.py` (`CajaModule`, the main panel).
- **`modules/mesero/`** — independent Flask server with PIN authentication and a REST API consumed by the web app (HTML + JS served by the backend). New orders for a table accumulate as "rounds" within the same order instead of creating new tickets.
- **`impresora_cocina.py`** — print queue with retries, so the app never blocks if the printer is disconnected or jams.
- **`inventario.py`** — deducts stock when an order is charged, first through manually configured links (any product) and otherwise through automatic keyword detection (meats).
- **`reportes.py`** — daily sales, history, best sellers, expenses and cash close, with Excel export via `openpyxl`.
- **`camaras.py`** / **`camaras_config.py`** — mosaic of up to 8 RTSP cameras from a HiLook/Hikvision NVR, each read in its own thread so the UI never freezes.
- **`dashboard_server.py`** — separate **read-only** Flask server for the owner, with its own password.
- **`licencia.py`** — per-machine activation.

## Database

Engine: **SQLite** (`data/restaurante.db`). Main tables:

| Table | Content |
|---|---|
| `pedidos` | One record per table/order (open, closed or cancelled) |
| `lineas_pedido` | Each product added to an order, with audited price editing |
| `rondas_pedido` | Successive "additions" to the same order (avoids duplicate tickets) |
| `pagos_pedido` | Audit of every payment (full, partial or split cash/transfer) |
| `historial_precios` | Record of each manual price edit, with reason and user |
| `gastos` | Daily expenses (used by the cash close) |
| `cierres_caja` | Cash-close history: cash, transfers, expenses, calculated difference |
| `cancelaciones_pedido` | Cancelled orders with reason and a snapshot of the ticket |
| `inventario` / `inventario_vinculos` | Stock of supplies and product → supply links |
| `comentarios_producto` | Predefined quick comments per product |

The **menu** (products and categories) lives separately in `data/menu.json`, managed by `MenuStore`.

## License / activation system

1. The first time the program runs on a PC, it computes a unique **machine code** (Windows MachineGuid, with MAC + hostname as fallback) and shows it on screen.
2. That code is sent to the software owner, who generates the matching **activation key** (HMAC-SHA256 of the machine code with a private secret).
3. When the key is entered, the program validates it and stores it in `data/.licencia`.
4. On every launch it re-checks that the machine code is still valid for the stored key; copying the folder to another PC changes the code and a new key is required.

This is a deterrent against casual copying, not DRM — it is not meant to be foolproof.

## Networking and ports

| Service | Port | Scope | Authentication |
|---|---|---|---|
| Waitstaff app (`modules/mesero`) | `5050` | Local WiFi only | PIN |
| Owner dashboard (`dashboard_server.py`) | `5051` | Designed to be exposed via Tailscale Funnel | Own password, different from the PIN |

Waitstaff never receive the dashboard URL or password; they are two completely separate servers.

## Notes about this public version

- Business data (database, menu, cash-close Excel files), activation keys and session secrets were removed; the app regenerates demo data on first run.
- The business name was replaced by a generic "Demo Restaurant" label.
- All credentials and secrets are read from `.env`; the defaults in the code are placeholders and **must be changed** for any real deployment.
- Source comments and docstrings were translated to English; user-facing UI text and identifiers remain in Spanish, since the application is used by Spanish-speaking staff.
