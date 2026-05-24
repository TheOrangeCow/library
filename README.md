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
<img width="1916" height="1035" alt="image" src="https://github.com/user-attachments/assets/25190bac-694c-4696-9d69-367ab1d88bcc" />

### Sevens Game
<img width="1913" height="1034" alt="image" src="https://github.com/user-attachments/assets/76050338-2c06-4f81-9c6e-6c5787b65bcc" />

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

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `KEY` | Yes | - | Secret key for Flask session management |
| `CORS_ORIGINS` | No | `http://localhost:5000` | Comma-separated list of allowed origins |
| `FLASK_DEBUG` | No | `false` | Enable/disable debug mode |

## Security Considerations

- **Secret Key:** Always use a strong, random secret key in production
- **CORS:** The application restricts cross-origin requests to configured origins
- **Input Validation:** All user inputs are validated and sanitized
- **Session Management:** User sessions are managed securely
- **Environment Variables:** Sensitive data (keys, origins) should be stored in `.env` and not committed to version control

## Development

### Running in Development Mode

Set `FLASK_DEBUG=true` in your `.env` file to enable Flask's auto-reload and debug toolbar:

```bash
FLASK_DEBUG=true python app.py
```

### Game Development

Each game is implemented as a separate module with its own blueprint. To add a new game:

1. Create a new folder: `games/newgame/`
2. Implement game logic in `newgame.py` with a Flask blueprint
3. Add HTML templates to `templates/`
4. Register the blueprint in `app.py`

## Deployment

### Production Deployment with Gunicorn

```bash
gunicorn --worker-class geventwebsocket.gunicorn.workers.GeventWebSocketWorker \
         --bind 0.0.0.0:5000 \
         --workers 4 \
         app:app
```

For production, ensure:
- `FLASK_DEBUG=false`
- A strong `KEY` is set in environment variables
- `CORS_ORIGINS` is set to your production domain(s)
- Consider using a reverse proxy (Nginx) in front of the application

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details.

## Troubleshooting

### "SECRET_KEY environment variable (KEY) not set!"
- **Solution:** Create a `.env` file with a `KEY` variable. See [Set up environment variables](#set-up-environment-variables)

### WebSocket connection errors
- **Solution:** Ensure your CORS_ORIGINS configuration matches your application's URL
- Check browser console for detailed error messages

### Port already in use
- **Solution:** Change the port in `app.py` or kill the process using port 5000:
  ```bash
  # Linux/Mac
  lsof -i :5000
  kill -9 <PID>
  
  # Windows
  netstat -ano | findstr :5000
  taskkill /PID <PID> /F
  ```

## Support

For issues and questions, please use the [GitHub Issues](https://github.com/TheOrangeCow/library/issues) page.
