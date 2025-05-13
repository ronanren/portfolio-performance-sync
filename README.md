# portfolio-performance-sync

Track your portfolio performance account and get real-time data via api and widgets.

## Development

Add your `portfolio.xml` file to the root of the project.

```bash
# Install dependencies
pip3 install -r requirements.txt

# Verify your holdings
python3 script.py USD

# Run the API
python3 run_api.py

# Get your portfolio in USD or EUR
curl -X GET "http://localhost/api/portfolio?base_currency=USD" -H "X-API-Key: key"
```

## Deploy

### Local Development

```bash
# Run the API locally
python3 run_api.py
```

### Deploy to Render

1. Create a free account on [Render](https://render.com)
2. Create a new Web Service
3. Upload your `portfolio.xml` file to the repo Github (private for privacy)
4. Connect your GitHub repository
5. Configure the service:

   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn api.main:app --host 0.0.0.0 --port $PORT`
   - Add your environment variables:
     - `PORT`: 80
     - `X_API_KEY`: Your API key
     - `API_KEY_NAME`: X-API-Key
     - `URL_RENDER`: Your Render URL

6. Deploy!

Your API will be available at `https://your-app-name.onrender.com`

## API

### Get Portfolio

```bash
curl -X GET "http://localhost/api/portfolio?base_currency=USD" -H "X-API-Key: key"
```

### Health Check

```bash
curl -X GET "http://localhost/api/health"
```
