# portfolio-performance-sync

Track your Portfolio Performance account and receive daily notifications with key updates and insights.

## Development

Add your `portfolio.xml` file to the root of the project.

```bash
# Install dependencies
pip3 install -r requirements.txt

# Verify your holdings
python3 script.py USD

# Run the API
python3 run_api.py

# Get your portfolio
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
3. Connect your GitHub repository
4. Configure the service:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python run_api.py`
   - Add your environment variables:
     - `PORT`: 8000
     - `X_API_KEY`: Your API key
5. Upload your `portfolio.xml` file to the service
6. Deploy!

Your API will be available at `https://your-app-name.onrender.com`
