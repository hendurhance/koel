<div align="center">
  <img src="/docs/images/koel-logo.png" alt="logo" width="300" height="auto" />
  <br/>
  <p>
    <b>💱 Koel is a free, open-source, self-hosted exchange rate API that aggregates real-time currency conversion data by scraping multiple sources, ensuring high availability and accuracy through an event-driven, fault-tolerant architecture.</b>
    <br/>
    <span>
      No usage limits, no API keys. Works great on client-side in the browser or mobile apps. You can deploy it on your own server or in a Docker container.
    </span>
  </p>
  <p>
    <a href="https://github.com/hendurhance/koel/issues/new?assignees=&labels=&template=bug_report.md&title=">Report Bug</a>
    ·
    <a href="https://github.com/hendurhance/koel/issues/new?assignees=&labels=&template=feature_request.md&title=">Request Feature</a>
  </p>
</div>

> If you are here to understand how this was built, you can check out the **[technical documentation](/docs/TECHNICAL_DOCUMENTATION.md)** for the system design, architecture, and design patterns used in this project. You can also check out the **[list of features](/docs/FEATURES.md)** to see what this project can do.

## Table of Contents
- [About Koel](#about-koel)
- [Features](#features)
- [Getting Started](#getting-started)
- [Installation](#installation)
- [Usage](#usage)
- [API Reference](#api-reference)
- [Sources](#sources)
- [Contributing](#contributing)
- [License](#license)

## About Koel

Koel is a free, open-source, self-hosted exchange rate API that provides real-time currency conversion data by aggregating information from multiple data sources through web scraping. Built on an event-driven, fault-tolerant architecture, Koel eliminates usage limits and API key requirements, giving you complete control over your currency data—whether you deploy it on your own server or within a Docker container.

## Features

- **Real-Time Data Aggregation:** Scrapes multiple sources to gather the latest exchange rates.
- **Self-Hosted:** Deploy Koel on your own infrastructure without relying on third-party APIs.
- **Fault-Tolerant:** Uses a factory pattern and multiple data sources to ensure data availability even if one source fails.
- **Event-Driven Architecture:** Background tasks powered by Celery for regular and scheduled scrapes.
- **High Performance:** Optimized for high-volume writes and fast read operations with techniques such as denormalization, bulk upserts, and partitioning.
- **No Usage Limits:** Enjoy unlimited requests with no API keys required.
- **Client-Side Friendly:** Easily integrate with browser or mobile applications.
- **Docker Support:** Containerize your deployment for consistency and ease of use.

## Getting Started

### Prerequisites

- **Python 3.8+** – The project is built with Python and uses modern asynchronous libraries.
- **PostgreSQL 10+** – Recommended for its native partitioning support.
- **Redis** – Used for caching, which is required for the application to run and keep track of jobs.
- **Celery** – For background tasks and scheduling.
- **Alembic** – For database migrations.
- **Docker & Docker Compose** (optional) – For containerized deployment.

### Clone the Repository

```bash
git clone https://github.com/hendurhance/koel.git
cd koel
```

## Installation
### Using Docker Compose
<!-- first bullet point in numbers -->
1. Build and Start the Containers:
```bash
docker-compose up -d --build
```
2. Access the API documentation:
```bash
http://localhost:8000/docs
```

### Local Installation
1. Create a virtual environment:
```bash
python3 -m venv venv
```
2. Activate the virtual environment:
```bash
# On Windows
venv\Scripts\activate
# On macOS/Linux
source venv/bin/activate
```
3. Install the required packages:
```bash
pip install -r requirements.txt
```
4. Create a `.env` file in the root directory and set the required environment variables:
```bash
cp .env.example .env
```
5. Update the `.env` file with your PostgreSQL database credentials and other configurations.
6. Install the database migrations:
```bash
alembic upgrade head
```
7. Run the seeders to populate the database with currency data:
```bash
python app/db/seed.py
```
8. Start the application:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
9. Access the API documentation:
```bash
http://localhost:8000/docs

# or
http://localhost:8000/redoc
```

## Usage
### API Endpoints
- **Get Currency List:**
  - `GET /api/currencies`
  - Returns a list of all available currencies.
  - Response:
    ```json
    {
        "success": true,
        "data": [
            {
            "id": 1,
            "name": "Euro",
            "name_plural": "euros",
            "code": "EUR",
            "symbol": "€",
            "decimal_digits": 2,
            "icon": null,
            "created_at": "2025-04-12T16:27:05.360172+01:00",
            "updated_at": "2025-04-12T16:27:05.360172+01:00"
            },
            {
            "id": 2,
            "name": "United Arab Emirates Dirham",
            "name_plural": "UAE dirhams",
            "code": "AED",
            "symbol": "AED",
            "decimal_digits": 2,
            "icon": null,
            "created_at": "2025-04-12T16:27:05.360172+01:00",
            "updated_at": "2025-04-12T16:27:05.360172+01:00"
            },
            ...
        }
    ]
    ```
- **Get Exchange Rate:**
  - `GET /api/rates?from=USD&to=EUR`
  - Query parameters:
    - `from`: The base currency code (e.g., USD).
    - `to`: The target currency code (e.g., EUR).
    - `amount`: The amount to convert (optional, default is 1).
  - Returns the exchange rate from one currency to another.
    - Response:
        ```json
        {
            "success": true,
            "data": {
                "id": 31329,
                "base_currency_id": 9,
                "target_currency_id": 1,
                "rate": 0.88019,
                "source": "trading-economics",
                "created_at": "2025-04-13T12:04:27.949186+01:00",
                "base_currency": {
                "id": 9,
                "name": "US Dollar",
                "name_plural": "US dollars",
                "code": "USD",
                "symbol": "$",
                "decimal_digits": 2,
                "icon": null,
                "created_at": "2025-04-12T16:27:05.360172+01:00",
                "updated_at": "2025-04-12T16:27:05.360172+01:00"
                },
                "target_currency": {
                "id": 1,
                "name": "Euro",
                "name_plural": "euros",
                "code": "EUR",
                "symbol": "€",
                "decimal_digits": 2,
                "icon": null,
                "created_at": "2025-04-12T16:27:05.360172+01:00",
                "updated_at": "2025-04-12T16:27:05.360172+01:00"
                },
                "amount": null,
                "converted_amount": null
            },
            "message": "Exchange rate retrieved successfully."
        }
        ```
- **Get Exchange Rate History:**
  - `GET /api/rates/history?from=USD&to=EUR&from_date=2025-04-01&to_date=2025-04-10`
  - Query parameters:
    - `from`: The base currency code (e.g., USD).
    - `to`: The target currency code (e.g., EUR).
    - `from_date`: The start date for the history (format: YYYY-MM-DD).
    - `to_date`: The end date for the history (format: YYYY-MM-DD).
  - Returns the historical exchange rates between two currencies.
    - Response:
        ```json
        {
            "success": true,
            "data": {
                "base": "USD",
                "target": "EUR",
                "rates": [
                    {
                        "id": 129,
                        "base_currency_id": 9,
                        "target_currency_id": 1,
                        "rate": 0.88019,
                        "source": "trading-economics",
                        "created_at": "2025-04-12T23:46:41.554303+01:00"
                    },
                    {
                        "id": 15537,
                        "base_currency_id": 9,
                        "target_currency_id": 1,
                        "rate": 0.88019,
                        "source": "trading-economics",
                        "created_at": "2025-04-13T11:34:08.462136+01:00"
                    },
                    {
                        "id": 31329,
                        "base_currency_id": 9,
                        "target_currency_id": 1,
                        "rate": 0.88019,
                        "source": "trading-economics",
                        "created_at": "2025-04-13T12:04:27.949186+01:00"
                    },
                    ...
                ]
            },
            "message": "Exchange rate history retrieved successfully."
        }
        ```
### Background Tasks
Koel uses Celery to run background tasks for scraping data from multiple sources. The tasks are defined in the `app/tasks/celery_app.py` directory. You can run the Celery worker using the following command:

```bash
celery -A app.tasks.celery_app worker --loglevel=info
```
This will start the Celery worker and listen for tasks to execute. You can also run the Celery beat scheduler to schedule periodic tasks:

```bash
celery -A app.tasks.celery_app beat --loglevel=info
```
### Caching
Koel uses Redis for caching the exchange rates to improve performance and run job and tasks. You can configure the caching settings in the `.env` file. By default, Koel uses a Redis instance running on `localhost:6379`. You can change the Redis URL in the `.env` file:
```env
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/1

REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=1
REDIS_PASSWORD=
```
### Database
Koel uses PostgreSQL as the database backend. You can configure the database settings in the `.env` file. By default, Koel uses a PostgreSQL instance running on `localhost:5432`. You can change the database URL in the `.env` file:
```env
DB_CONNECTION=postgresql
DB_HOST=localhost
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=
DB_NAME=koel
```
## Sources
Koel scrapes data from multiple sources to provide accurate and up-to-date exchange rates. The sources are defined in the `app/scraping/sources` directory. You can add or modify the sources by creating new classes that extend the `BaseScraper` class.
### Supported Sources
| Source Name | Description | Source URL | Pair Type |
| ----------- | ----------- | ---------- | ---- |
| [Trading Economics](https://tradingeconomics.com/) | Provides real-time exchange rates and economic data. | [tradingeconomics.com](https://tradingeconomics.com/) | Multi Pair |
| [Exchange Rates Org Uk](https://exchangerates.org.uk/) | Provides exchange rates and currency conversion data. | [exchangerates.org.uk](https://exchangerates.org.uk/) | Multi Pair |
| [Currency Converter Org Uk](https://www.currencyconverter.org.uk) | Provides currency conversion data and exchange rates. | [currencyconverter.co.uk](https://www.currencyconverter.org.uk) | Multi Pair |
| [X-Rates](https://www.x-rates.com/) | Provides exchange rates and currency conversion data. | [x-rates.com](https://www.x-rates.com/) | Multi Pair |
| [Forbes](https://www.forbes.com/) | Provides exchange rates and financial news. | [forbes.com](https://www.forbes.com/) | Single Pair |
| [Hexa Rates](https://hexarate.paikama.co) | Provides exchange rates and currency conversion data. | [hexarate.paikama.co](https://hexarate.paikama.co) | Single Pair |
| [FxEmpire](https://fxempire.com/) | Provides exchange rates and financial news. | [fxempire.com](https://fxempire.com/) | Single Pair |
| [Oanda](https://www.oanda.com/) | Provides exchange rates and financial data. | [oanda.com](https://www.oanda.com/) | Single Pair |
| [Wise](https://wise.com/) | Provides exchange rates and currency conversion data. | [wise.com](https://wise.com/) | Single Pair |
| [Xe](https://xe.com/) | Provides exchange rates and currency conversion data. | [xe.com](https://xe.com/) | Single Pair |


## Contributing
We welcome contributions to Koel! If you would like to contribute, please follow these steps:
1. Fork the repository.
2. Create a new branch for your feature or bug fix:
```bash
git checkout -b feature/your-feature-name
```
3. Make your changes and commit them:
```bash
git commit -m "Add your feature or fix"
```
4. Push your changes to your forked repository:
```bash
git push origin feature/your-feature-name
```
5. Create a pull request to the main repository.
6. Describe your changes and why they should be merged.
7. Wait for feedback and make any necessary changes.
8. Once approved, your changes will be merged into the main repository.

## License
Koel is licensed under the [MIT License](LICENSE). Feel free to use, modify, and distribute this software as per the terms of the license.

## Acknowledgments
- [FastAPI](https://fastapi.tiangolo.com/) - The web framework used for building the API.
- [Celery](https://docs.celeryproject.org/en/stable/) - The task queue used for background tasks.
- [Redis](https://redis.io/) - The in-memory data structure store used for caching and job tracking.
- [PostgreSQL](https://www.postgresql.org/) - The database used for storing exchange rates and currency data.
- [Alembic](https://alembic.sqlalchemy.org/en/latest/) - The database migration tool used for managing schema changes.
- [Docker](https://www.docker.com/) - The containerization platform used for deploying Koel.
- [Docker Compose](https://docs.docker.com/compose/) - The tool used for defining and running multi-container Docker applications.
- [Pydantic](https://pydantic-docs.helpmanual.io/) - The data validation and settings management library used for defining data models.
- [SQLAlchemy](https://www.sqlalchemy.org/) - The SQL toolkit and Object-Relational Mapping (ORM) library used for database interactions.
- [Beautiful Soup](https://www.crummy.com/software/BeautifulSoup/) - The library used for web scraping and parsing HTML.
- [Requests](https://docs.python-requests.org/en/latest/) - The library used for making HTTP requests.

## 👥 Authors 
- Endurance - [Github](https://github.com/hendurhance) - [Twitter](https://twitter.com/hendurhance) - [LinkedIn](https://www.linkedin.com/in/hendurhance/)