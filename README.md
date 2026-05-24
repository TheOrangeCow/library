# Library

A Flask-based web application featuring multiple card and casino games with real-time multiplayer capabilities using WebSocket.

## Games Supported
- Pooheads
- Sevens
- Blackjack
- Poker
- Slots

## Features
- Real-time multiplayer gaming with WebSocket support
- User authentication and session management
- Chip-based currency system
- Leaderboards and player statistics
- Global and private messaging
- User achievements and activity tracking
- Responsive web interface

## Screenshots

### Home Page
<img width="1913" height="1033" alt="image" src="https://github.com/user-attachments/assets/dd7d86fa-1314-4973-9fae-f40cf61cd6e3" />

### Pooheads Game
<img width="717" height="476" alt="image" src="https://github.com/user-attachments/assets/d1b78a21-6778-4a80-981f-54a06d7371fe" />




## Installation

### Prerequisites
- Python 3.7 or higher
- pip (Python package manager)

### Setup Instructions

1. **Clone the repository**
   ```bash
   git clone https://github.com/TheOrangeCow/library.git
   cd library
   ```

2. **Create a virtual environment** (recommended)
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   Create a `.env` file in the root directory:
   ```bash
   # Required: Secret key for session management (generate a secure random string)
   KEY=your-secure-secret-key-here
   
   # Optional: CORS allowed origins (defaults to localhost:5000)
   CORS_ORIGINS=http://localhost:5000,https://yourdomain.com
   
   # Optional: Enable debug mode (set to 'true' to enable)
   FLASK_DEBUG=false
   ```
   
   **Important:** Generate a secure `KEY` value:
   ```python
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

5. **Run the application**
   ```bash
   python app.py
   ```
   
   The application will be available at `http://localhost:5000`

## Project Structure

```
library/
├── app.py                 # Main application entry point
├── core.py               # Flask and SocketIO configuration
├── requirements.txt      # Python dependencies
├── .env                  # Environment variables (not in version control)
├── .gitignore            # Git ignore rules
├── auth/                 # Authentication module
├── pooheads/            # Pooheads game logic
├── sevens/              # Sevens game logic
├── blackjack/           # Blackjack game logic
├── poker/               # Poker game logic
├── slots/               # Slots game logic
├── templates/           # HTML templates
└── static/              # Static files (CSS, JS, images)
```

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details.
