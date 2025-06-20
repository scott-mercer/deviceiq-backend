# DeviceIQ Backend

A FastAPI backend for processing device analytics CSV uploads, with logging, monitoring, and API key protection.

## Features

- **CSV Upload & Analytics** endpoints
- **API Key** authentication
- **Structured logging** (console, Sentry integration)
- **Prometheus** metrics (`/metrics` endpoint)
- **Sentry** error and log monitoring
- **CORS** enabled for frontend integration

## Requirements

- Python 3.8+
- See `requirements.txt` for dependencies

## Setup

1. **Clone the repo:**
   ```sh
   git clone https://github.com/yourusername/deviceiq-backend.git
   cd deviceiq-backend
   ```

2. **Create and activate a virtual environment:**
   ```sh
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```sh
   pip install -r requirements.txt
   ```

4. **Configure environment variables:**

   Create a `.env` file in the project root:
   ```
   SENTRY_DSN=your-sentry-dsn
   ```

   *(Replace `your-sentry-dsn` with your actual Sentry DSN)*

5. **Run the server:**
   ```sh
   uvicorn app:app --reload
   ```

6. **Access the API docs:**
   - [http://localhost:8000/docs](http://localhost:8000/docs)

## API Endpoints

- `POST /upload-csv/`  
  Upload a CSV file and get device coverage matrix.

- `POST /analytics/`  
  Upload a CSV file and get grouped analytics.

## Monitoring

- **Prometheus metrics:**  
  Visit [http://localhost:8000/metrics](http://localhost:8000/metrics)

- **Sentry:**  
  Errors and warnings are sent to your configured Sentry project.

## License

MIT
