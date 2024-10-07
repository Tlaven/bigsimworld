Here's the updated README with your requested modifications:

```markdown
# BigSimWorld

## Overview
BigSimWorld is a simulation project utilizing Python for the backend and Vue.js for the frontend, designed to simulate large-scale environments and interactions.

## Features
- Interactive simulation visualization with Vue.js
- Data processing and API endpoints managed by a Python backend
- SQLite3 for lightweight database management
- Redis for caching and real-time data handling

## Project Structure
```bash
# Project directory structure

.
├── app/
│   ├── api/                # API endpoints
│   ├── core/               # Core functionality (generation, simulation, statistics)
│   ├── models/             # Database models and processing
│   ├── schemas/            # JSON schemas for API
│   ├── services/           # Services for data handling
│   └── utils/              # Utility functions
├── LICENSE                  # Project license
├── logs/                   # Log files
├── run.py                  # Main script to run the simulation
└── web/
    ├── package.json
    ├── src/
    │   ├── App.vue
    │   ├── components/      # Reusable Vue components
    │   ├── plugins/         # Vue plugins
    │   ├── router/          # Vue router configuration
    │   └── views/           # Main views for the application
    └── vite.config.mjs      # Vite configuration
```

## Setup Instructions

### Backend (Python)
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Run the backend:
   ```bash
   python run.py
   ```

### Frontend (Vue.js)
1. Navigate to the `web` directory:
   ```bash
   cd web
   ```
2. Install frontend dependencies:
   ```bash
   pnpm install
   ```
3. Start the frontend:
   ```bash
   pnpm dev
   ```

## API
The project provides RESTful endpoints for interaction. Sample endpoints:
- `/api/v1/subscribe/get-client-id`: Retrieves a unique client ID for the user.
- `/api/v1/subscribe/notify-connection`: Notifies the server that the client has connected.
- `/api/v1/subscribe/unsubscribe/<client_id>`: Unsubscribes the client from the simulation.

## License
This project is licensed under the MIT License.
```

### Key Changes:
- Added sections for SQLite3 and Redis under **Features**.
- Maintained the structure and clarity of the project details.
- Included descriptions of sample API endpoints.

Feel free to adjust any specific details as needed!