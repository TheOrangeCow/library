# The Library

A self-hosted multiplayer gaming platform built by [TheOrangeCow](https://github.com/TheOrangeCow).

Library is a collection of online multiplayer games combined into one platform.

It includes real-time games, accounts, leaderboards, chat, and an expanding collection of games.

The aim:

> Build a place where classic card games can live together, be played with friends, and be customised by anyone.

---

# Features

## Multiplayer Games

Library currently includes:

* Pooheads
* Sevens
* Blackjack
* Poker
* White Jack
* Crash
* Enraged Pooheads
* Slots
* Egyptian Rat screw

More games are actively being developed.

Coming soon:

* Horse Racing
* Happy Families
* More card 

---

# Real-Time Gameplay

Library uses WebSockets to provide live multiplayer gameplay.

Features:

* Real-time player updates
* Multiplayer rooms
* Live game actions
* Turn handling
* Chat system
* Instant game state changes

---

# Accounts

Players can create accounts or used their <b> cow account</b> and track their progress.

Features:

* User profiles
* Statistics
* Leaderboards
* Saved data
* Future achievements system

---

# Leaderboards

Compete against other players.

Supports:

* Wins
* Scores
* Rankings
* Game statistics

---

# Technology

## Backend

* Python
* Flask
* Flask-SocketIO

## Frontend

* HTML
* CSS
* JavaScript

## Communication

* WebSockets
* Socket.IO

## Database

Used for:

* Accounts
* Player data
* Game information

---

# Run Your Own Server

Anyone can host their own copy of Library.

## Requirements

You need:

* Python 3.10+
* Git
* A computer or server

---

# Installation

Clone the repository:

```bash
git clone https://github.com/TheOrangeCow/library.git
```

Enter the project:

```bash
cd library
```

Create a virtual environment:

```bash
python -m venv venv
```

Activate it.

Windows:

```bash
venv\Scripts\activate
```

Linux/macOS:

```bash
source venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

---

# Configuration

Create a `.env` file.

Example:

```env
SECRET_KEY=your_secret_key
DATABASE_URL=your_database
```

Change these values for your setup.

---

# Starting The Server

Run:

```bash
python app.py
```

The website will start at:

```
http://localhost:5000
```

---

#  Adding New Games

Library is designed to expand.

A new game should include:

* Game logic
* Player handling
* WebSocket events
* Frontend interface
* Rules

The goal is to make adding new games simple.

---

# Contributing

Contributions are welcome.

You can help by:

* Adding new games
* Fixing bugs
* Improving the UI
* Improving performance
* Suggesting features

Steps:

1. Fork the repository

2. Create a branch:

```bash
git checkout -b feature/new-game
```

3. Make your changes

4. Commit:

```bash
git commit -m "Added new game"
```

5. Push:

```bash
git push origin feature/new-game
```

6. Open a Pull Request

---

# Reporting Bugs

Found a problem?

Open an issue:

https://github.com/TheOrangeCow/library/issues

Include:

* What happened
* What you expected
* Steps to reproduce
* Screenshots if possible

---

# Support The Project

If you like Library:

* Star the GitHub repository

* Share it with friends

* Add new games

* Contribute improvements

Every star helps the project grow.

---

# Links

Website:

https://library.theorangecow.org

GitHub:

https://github.com/TheOrangeCow/library

Developer:

https://github.com/TheOrangeCow

---

# License

This project is open source.

See the repository license for details.

---

Built with too many tabs open<div style="text-align: right"> //moo </div>
