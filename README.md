# portfolio-performance-sync

Track your Portfolio Performance account and receive daily notifications with key updates and insights.

## Development

Add your `portfolio.xml` file to the root of the project.

```bash
pip3 install -r requirements.txt
```

```bash
python3 script.py USD

python3 run_api.py

curl -X GET "http://localhost:8000/api/portfolio?base_currency=USD" -H "X-API-Key: key"
```
