# KOEL - Technical Documentation


## Table of Contents
- [KOEL - Technical Documentation](#koel---technical-documentation)
  - [Table of Contents](#table-of-contents)
  - [Overview](#overview)
    - [Objectives](#objectives)
  - [Problem Statement](#problem-statement)
    - [Why build this?](#why-build-this)
    - [Key Challenges](#key-challenges)
  - [System Architecture](#system-architecture)
  - [Design Decisions](#design-decisions)
    - [Event-Driven Architecture](#event-driven-architecture)
    - [Multiple Data Sources \& Factory Pattern](#multiple-data-sources--factory-pattern)
    - [Scraper Manager and Failsafe Mechanism](#scraper-manager-and-failsafe-mechanism)
    - [Rate Limiting \& User-Agent Rotation](#rate-limiting--user-agent-rotation)
    - [Database Design \& Partitioning](#database-design--partitioning)
    - [Redis Caching](#redis-caching)
    - [Dockerization](#dockerization)
  - [Data Flow / Sequence Diagram](#data-flow--sequence-diagram)
  - [Database Schema and Partitioning](#database-schema-and-partitioning)
    - [Currencies Table](#currencies-table)
    - [Exchange Rates Table](#exchange-rates-table)
  - [Project Structure](#project-structure)
  - [Detailed Implementation Notes](#detailed-implementation-notes)
    - [ETL Flow](#etl-flow)
    - [Scraper Sources](#scraper-sources)
    - [Data Acquisition Strategy](#data-acquisition-strategy)
      - [Currency Classification](#currency-classification)
    - [Controllers, Services, and Schemas](#controllers-services-and-schemas)
    - [Celery Tasks and Scheduling](#celery-tasks-and-scheduling)
    - [API Implementation](#api-implementation)
  - [Performance Optimizations](#performance-optimizations)
    - [Database Indexes](#database-indexes)
    - [Redis Caching Implementation](#redis-caching-implementation)
  - [Scaling Considerations](#scaling-considerations)
    - [Database Scaling](#database-scaling)
    - [Caching Strategies](#caching-strategies)
    - [Application Scaling](#application-scaling)
  - [Deployment](#deployment)
  - [Monitoring and Logging](#monitoring-and-logging)
  - [Future Enhancements](#future-enhancements)

## Overview

Koel is a self-hosted currency exchange ETL (Extract, Transform, Load) solution that scrapes exchange rate data from multiple external websites and offers a REST API for currency conversion. The system avoids reliance on third-party APIs with usage or rate limits. Instead, it directly scrapes HTML from established (mostly universal or widely recognized) currency rate websites.

### Objectives

- **High Availability**: If one source fails (rate-limited, server down, etc.), Koel falls back to other sources.
- **Performance**: Must handle scraping thousands of currency pairs daily and serve hundreds of thousands of inbound requests.
- **Scalable Database**: Partition large exchange rate tables to efficiently handle high read/write throughput.
- **Extensibility**: Add new data sources easily (via a unified BaseScraper and a factory-driven approach).
- **Self-Hosted**: Docker-based deployment for easy set-up and horizontal scaling.

## Problem Statement

### Why build this?

1. **Availability Constraints**: Existing publicly available currency converter APIs often impose usage limitations or require API keys.
2. **Reliability Issues**: Relying on one exchange rate data source is risky due to potential downtime, rate-limiting, or data anomalies.
3. **Source Independence**: We need a reliable service that aggregates or switches between data sources automatically.

### Key Challenges

1. **Data Acquisition**: 
   - Not all websites provide a JSON API; most only present HTML
   - Exchange rates must be continuously updated from reliable sources
   - No single source guarantees 100% uptime or unlimited access

2. **Data Volume & Management**: 
   - With up to 155 currencies, collecting rates for each pair can generate ~155×154 = 23,870 records per complete scrape
   - In a single week at multiple scrapes per day, data grows large quickly
   - As exchange rate history accumulates, database performance can degrade without proper optimization

3. **Performance Requirements**:
   - The API must handle hundreds of thousands of requests per day while maintaining low latency
   - Must serve large volumes of API requests efficiently

4. **System Reliability**:
   - The service must remain available even when individual data sources fail or rate-limit our requests
   - If a site goes down, the system should keep functioning using alternative sources

## System Architecture

Koel is built with a multi-layered architecture that separates concerns and provides clear interfaces between components.

```mermaid
flowchart TB
    A["Celery Tasks<br/>(Scrape, ETL)"] -- "Scraped Rates" --> B["PostgreSQL<br/>(Partitioned Exchange Rates)"]
    A --> C["Redis Cache"]
    B --> D["FastAPI<br/>Controllers"]
    C --> D
    D --> E["REST API Clients<br/>(Users)"]
```

Breaking this down by layers:

1. **API Layer (FastAPI)**: 
   - Exposes REST endpoints for currency data retrieval
   - Handles HTTP requests, authentication, rate limiting
   - Serves API documentation

2. **Service Layer (Controllers)**:
   - Implements business logic for currency and exchange rate operations
   - Mediates between the API layer and data access layer

3. **Cache Layer (Redis)**:
   - Caches frequently requested data (e.g., currency lists, recent exchange rates)
   - Reduces database load for common queries

4. **Database Layer (PostgreSQL)**:
   - Partitioned storage for high-write, high-read workflows
   - Efficiently stores and retrieves large volumes of exchange rate data

5. **ETL Process (Celery)**:
   - Executes ETL jobs (scraping, transformation, loading) asynchronously
   - Scheduled via Celery Beat to run at specific intervals

**Why this architecture?**
- **Separation of concerns**: Each component has a single responsibility, making the system easier to maintain and extend
- **Loose coupling**: Components interact through well-defined interfaces, allowing us to replace or modify components individually
- **Scalability**: Each layer can be scaled independently based on demand
- **Resilience**: Failures in one component don't necessarily cause failures in others

## Design Decisions

### Event-Driven Architecture

**Why event-driven?**

1. **Scheduled Operations**: Scraping operations happen at specific intervals (e.g., every 6 hours for "primary" currencies, every 12 hours for "secondary").
2. **Background Processing**: ETL operations can be resource-intensive and are better handled asynchronously.
3. **Decoupling**: A simple cron-like approach with Celery Beat ensures robust scheduling with minimal overhead.
4. **Resilience**: Failed tasks can be retried without affecting the API's availability.

### Multiple Data Sources & Factory Pattern

**Why multiple sources?**

1. **Reliability**: Circumvent rate limits or server downtime from any single source.
2. **Coverage**: Ensure availability of rates for currencies not supported by certain sites.
3. **Accuracy**: Cross-reference rates from multiple sources for validation.

**Why a factory pattern?**

```mermaid
classDiagram
    class BaseScraper {
        +BaseScraper(base_currency: str, target_currency: str = None)
        +extract() str
        +transform(raw_data: Any) dict
        +get_source_name() str
        +scrape() dict
    }
    
    class ExchangeRatesOrgUkScraper {
        +__init__(base_currency: str, target_currency: str = None,...)
        +extract() str
        +transform(raw_data: Any) dict
        +get_source_name() str
        +scrape() dict
    }
    
    class XEScraper {
        +__init__(base_currency: str, target_currency: str = None, ...)
        +extract() str
        +transform(raw_data: Any) dict
        +get_source_name() str
        +scrape() dict
    }
    
    class ScraperManager {
        +__init__(self, source_priority: List[str] = None, rate_limit_delay: float = 1.2)
        +_apply_rate_limit(self)
        + scrape_with_failsafe(self, base_currency: str, target_currencies: List[str] = None, ...)
    }
    
    BaseScraper <|-- ExchangeRatesOrgUkScraper
    BaseScraper <|-- XEScraper
    ScraperManager ..> BaseScraper
    ScraperManager ..> ExchangeRatesOrgUkScraper
    ScraperManager ..> XEScraper
```

1. **Abstraction**: All scrapers conform to the same interface (`extract()`, `transform()`, `scrape()`) regardless of how the source site formats its data.
2. **Extensibility**: To add a new site, simply create a new subclass of `BaseScraper` and register it in the factory (`SCRAPER_SOURCES`). No existing code must be heavily refactored.
3. **Encapsulation**:Each scraper’s implementation details (HTML parsing, building a URL, etc.) remain self-contained.
4. **Testability**: Because each site has a subclass, you can mock or stub a particular scraper during testing without affecting others.
The `ScraperManager` can also be tested by substituting in mock scraper objects.

### Scraper Manager and Failsafe Mechanism

**Why a manager?**

```mermaid
sequenceDiagram
    participant CT as Celery Task
    participant SM as ScraperManager
    participant DB as Database
    participant S1 as Source #1 (Multi-Pair)
    participant S2 as Source #2 (Multi-Pair)
    participant S3 as Source #3 (Single-Pair)
    
    CT->>SM: scrape_with_failsafe(base_currency, <br/>target_currencies, base_name, ...)
    note right of SM: 1) Check multi-pair sources<br/>2) If fail, fallback to single-pair
    
    alt Multi-Pair Attempt #1
        SM->>S1: extract() + transform()
        note over S1: Some failure (e.g. <br/>rate limit / server down)
        S1-->>SM: Exception or empty rates
    end
    
    alt Multi-Pair Attempt #2
        SM->>S2: extract() + transform()
        note over S2: Successful scraping
        S2-->>SM: { "USD":1.0, "EUR":0.9, ... }
        SM-->>SM: Rates collected
    else All Multi-Pair Failed
        note over SM: Fallback to single-pair logic
        SM->>S3: for each target_currency...
        S3-->>SM: partial or full success
    end
    
    SM->>DB: Bulk insert/update exchange_rates
    DB-->>SM: Success
    SM-->>CT: Return success status

```

1. **Prioritization**: We maintain a fallback priority order. If Source A fails, we try Source B, and so on.
2. **Fault Tolerance**: Continues operation even when some sources fail.
3. **Automatic Failover**: Tries alternative sources without service interruption.
4. **Centralized Control**: Single point for scraping policy decisions.

**Why failsafe?**

1. **Graceful Degradation**: If all multi-pair scrapers fail, we revert to single-pair scrapers for each currency pair.
2. **Availability**: This ensures we can still gather data, even if the "bulk" scraping endpoints become unavailable.
3. **Completeness**: Even if only partial data can be retrieved, the system can still function.

### Rate Limiting & User-Agent Rotation

1. **Request Rate Limiting**: Ensures we do not exceed "aggressive scraping" thresholds, e.g., ~50 requests per minute (1.2s intervals).
2. **User-Agent Rotation**: Randomly selects from a pool of user agents for each request to reduce the risk of being blocked or flagged as a bot.
3. **Request Delays**: Adds random delays between requests to mimic human behavior.

**Why these precautions?**
1. **Avoid Blocking**: Prevents being identified as a scraper
2. **Resource Respect**: Minimizes impact on source websites
3. **Reliability**: Reduces likelihood of being rate-limited
4. **Longevity**: Ensures sources remain available for longer periods

### Database Design & Partitioning

**Why this design?**

1. **Normalization**: Currency data is stored only once, avoiding redundancy
2. **Performance**: Optimized schema for frequent read/write operations
3. **Scalability**: Structure supports growth in data volume

**Why partitioning?**
> If you are familiar with the parent and child design in database optimization, the concept of partitioning is similar. The parent table is the main table in this instance `exchange_rates`, while the child tables are the monthly partitions (e.g., `exchange_rates_2025_04`). The write operation is done on the parent table, and then asynchronously, the data is also written to the child table. During read operations, the query is directed to the child table for faster access.
1. **Query Performance**: Partitioning improves query speed for large tables by splitting data into smaller monthly "child" tables
2. **Maintenance**: Old partitions can be compressed or archived easily
3. **Write Distribution**: Reduces contention on write-heavy tables
4. **Parallel Operations**: Different partitions can be accessed concurrently

### Redis Caching

**Why Redis?**

1. **Performance**: Frequently fetched data (e.g., "USD → EUR" rate) is cached to speed up API responses and reduce DB load
2. **Efficiency**: Avoid repeating expensive aggregator queries by short-term caching
3. **Speed**: In-memory data store with sub-millisecond response times
4. **TTL Support**: Automatic expiration of cached items
5. **Scalability**: Can be clustered for higher throughput

### Dockerization

**Why Docker?**

1. **Consistency**: Ensures the same environment across development, staging, and production
2. **Isolation**: Each component runs in its own container
3. **Scalability**: Easy to scale individual components
4. **Portability**: Can be deployed on any system supporting Docker
5. **Resource Efficiency**: Fine-grained control over resource allocation
6. **Orchestration**: Facilitates easy deployment and scaling in container orchestration platforms

## Data Flow / Sequence Diagram

Below is a detailed sequence diagram showing how scraping and serving a request work together:

```mermaid
sequenceDiagram
    autonumber
    participant CeleryBeat as Celery Beat
    participant CeleryTask as Celery Worker (Scrape Task)
    participant Manager as ScraperManager
    participant Source as ExchangeRate Site
    participant DB as Postgres
    participant Cache as Redis
    participant API as FastAPI Controller
    participant Client as API Client

    CeleryBeat->>CeleryTask: Trigger scrape task (every 6/12 hours)
    CeleryTask->>Manager: Attempt multi-pair scraping (factory approach)
    alt Multi-pair success
        Manager->>Source: GET rates HTML
        Source-->>Manager: HTML response
        Manager->>Manager: transform -> { "EUR": 1.012, "GBP":0.89, ... }
    else Multi-pair fails
        Manager->>Manager: Fallback single-pair
        Manager->>Source: GET single (e.g. "EUR" rate)
        Source-->>Manager: Single pair result
    end
    CeleryTask->>DB: Bulk insert new exchange rates
    CeleryTask->>Cache: Possibly flush or update relevant cache entries
    
    Client->>API: Request rate (e.g. USD to EUR)
    API->>Cache: Check if rate is in cache
    alt Cache HIT
        Cache-->>API: Return rate
    else Cache MISS
        API->>DB: Query latest rate
        DB-->>API: Return rate
        API->>Cache: Store newly fetched data
    end
    API-->>Client: Final JSON response
```

This sequence diagram illustrates:
1. How scheduled tasks trigger the scraping process
2. The fallback mechanism when primary scraping methods fail
3. How data flows from sources to the database
4. How API requests are served with caching

## Database Schema and Partitioning

### Currencies Table

The `currencies` table stores static metadata about each currency:

```
id (PK)
name
name_plural
code (unique)
symbol
decimal_digits
icon
created_at
updated_at
```

### Exchange Rates Table

The `exchange_rates` table is partitioned by month to manage the high volume of data:

```
id (SERIAL)
base_currency_id (FK -> currencies.id)
target_currency_id (FK -> currencies.id)
rate (FLOAT)
source (VARCHAR 50)
created_at (TIMESTAMPTZ)
```

**Partitioning Strategy**:

The table is partitioned by RANGE on `created_at` with monthly partitions, e.g., `exchange_rates_2025_04` for April 2025.

Each partition holds all records for the date range `[YYYY-MM-01, YYYY-(MM+1)-01)`.

**Why monthly partitions?**

1. **Size Management**: Monthly partitions store approximately 1.5 million rows each, balancing granularity and management overhead.
2. **Query Performance**: Queries for specific date ranges access only relevant partitions.
3. **Maintenance**: Archiving older partitions is straightforward (drop old partitions or move them to cold storage if needed).
4. **Scalability**: Can distribute partitions across different storage systems if needed.

```sql
-- Example of partitioning setup in PostgreSQL
 CREATE TABLE exchange_rates (
      id SERIAL,
      base_currency_id INTEGER NOT NULL,
      target_currency_id INTEGER NOT NULL,
      rate FLOAT NOT NULL,
      source VARCHAR(50) NOT NULL,
      created_at TIMESTAMPTZ NOT NULL,
      CONSTRAINT fk_exchange_rates_base_currency FOREIGN KEY (base_currency_id) REFERENCES currencies(id),
      CONSTRAINT fk_exchange_rates_target_currency FOREIGN KEY (target_currency_id) REFERENCES currencies(id),
      CONSTRAINT pk_exchange_rates PRIMARY KEY (id, created_at),
      CONSTRAINT unique_exchange_rates UNIQUE (base_currency_id, target_currency_id, created_at)
  ) PARTITION BY RANGE (created_at);

-- Create monthly partitions
CREATE TABLE exchange_rates_2025_04 PARTITION OF exchange_rates
    FOR VALUES FROM ('2025-04-01') TO ('2025-05-01');
    
CREATE TABLE exchange_rates_2025_05 PARTITION OF exchange_rates
    FOR VALUES FROM ('2025-05-01') TO ('2025-06-01');
```

## Project Structure

Below is the high-level structure of the repository:

```
.
├── alembic
│   ├── env.py
│   ├── README
│   ├── script.py.mako
│   └── versions
│       └── cfc173228e49_initial_migration.py
├── alembic.ini
├── app
│   ├── __init__.py
│   ├── api
│   │   ├── __init__.py
│   │   └── route.py
│   ├── controllers
│   │   ├── __init__.py
│   │   ├── currency_controller.py
│   │   └── exchange_rate_controller.py
│   ├── core
│   │   └── config.py
│   ├── db
│   │   ├── __init__.py
│   │   ├── currencies.json
│   │   ├── database.py
│   │   └── seed.py
│   ├── exceptions.py
│   ├── main.py
│   ├── models
│   │   ├── __init__.py
│   │   └── models.py
│   ├── schemas
│   │   ├── __init__.py
│   │   ├── api_response.py
│   │   └── schema.py
│   ├── scraping
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── factory.py
│   │   ├── manager.py
│   │   └── sources
│   │       ├── __init__.py
│   │       ├── currency_converter.py
│   │       ├── exchange_rates_org.py
│   │       ├── forbes.py
│   │       ├── fx_empire.py
│   │       ├── hexarate.py
│   │       ├── oanda.py
│   │       ├── trading_economics.py
│   │       ├── wise.py
│   │       ├── xe.py
│   │       └── xrates.py
│   ├── tasks
│   │   ├── __init__.py
│   │   ├── celery_app.py
│   │   ├── exchange_rates.py
│   │   ├── maintenance.py
│   │   └── progress_tracker.py
│   ├── user_agents.txt
│   └── utils
│       ├── __init__.py
│       ├── cache_manager.py
│       ├── custom_logger.py
│       ├── helpers.py
│       └── user_agent_rotator.py
├── celerybeat-schedule.db
├── docker-compose.yml
├── docker-entrypoint.sh
├── Dockerfile
├── docs
│   ├── FEATURES.md
│   ├── images
│   │   └── koel-logo.png
│   └── TECHNICAL_DOCUMENTATION.md
├── LICENSE
├── logs
│   └── app.log
├── README.md
└── requirements.txt
```

This structure follows a modular organization that separates different concerns:
- API routes and controllers
- Database models and schemas
- Scraping logic and sources
- Background tasks
- Utility functions
- Deployment configuration

## Detailed Implementation Notes

### ETL Flow

The ETL (Extract, Transform, Load) process is central to Koel's operation:

**Extract**:
- `extract()` method uses `requests` to fetch HTML from a data source
- Uses a random user-agent to avoid detection
- Implements timeouts and exception handling
- Different sources require different extraction approaches

**Transform**:
- `transform()` uses BeautifulSoup to parse HTML and map currency codes to exchange rates
- Normalizes data from different sources into a consistent format
- Returns a dictionary mapping currency codes to rates, e.g. `{ "EUR": 1.234, "GBP": 0.892, ... }`

**Load**:
- Bulk insert into `exchange_rates` partitioned table via SQLAlchemy's `insert` with `on_conflict_do_update`
- If a record with the same `(base_currency_id, target_currency_id, created_at)` already exists, we update the rate and source
- Optimized for high-volume insertions

### Scraper Sources

Each source is implemented as a separate class that inherits from the `BaseScraper`:

1. **Source Classification**:
   - **Base-Target Sources**: Require both base and target currencies in the request URL
     - Example: `https://example.com/convert?from=USD&to=EUR`
     - One request yields one exchange rate
   - **Base-Only Sources**: Require only the base currency and return rates for multiple targets
     - Example: `https://example.com/rates?base=USD`
     - One request yields multiple exchange rates

2. **Source Implementation**:
   - Each source is represented by a file under `app/scraping/sources/`
   - For example, `trading_economics.py` might scrape tradingeconomics.com
   - Single-pair or multi-pair capabilities are differentiated via an Enum
   - The `factory.py` enumerates all possible sources and injects them into the `ScraperManager`

**Example Sources**:
- exchange_rates_org.py
- xe.py
- trading_economics.py
- wise.py
- currency_converter.py
- forbes.py
- fx_empire.py
- oanda.py
- hexarate.py
- xrates.py

**Why this classification?**
1. **Efficiency**: Base-only sources require fewer requests
2. **Adaptability**: Works with different website structures
3. **Rate Limit Management**: Can prioritize more efficient sources

### Data Acquisition Strategy

#### Currency Classification

Currencies are classified into two groups:
1. **Primary Currencies**: Heavily traded currencies (USD, EUR, GBP, JPY, etc.)
2. **Secondary Currencies**: Less frequently traded currencies

**Scraping Frequency Calculation**:

**Primary Currencies (15)**:
- Scrape frequency: Every 6 hours (4 times per day)
- Pairs with all currencies (15 × 154 = 2,310)
- Daily records: 2,310 × 4 = 9,240

**Secondary Currencies (140)**:
- Scrape frequency: Every 12 hours (2 times per day)
- Pairs with all currencies (140 × 154 = 21,560)
- Daily records: 21,560 × 2 = 43,120

**Total daily records**: 9,240 + 43,120 = 52,360

Weekly: 52,360 × 7 = 366,520
Monthly: 52,360 × 30 ≈ 1.57 million

**Why this classification?**
1. **Resource Optimization**: More frequent updates for important currencies
2. **Rate Limit Management**: Spreads requests to avoid hitting rate limits
3. **Data Freshness**: Ensures critical rates are updated more frequently
4. **Storage Efficiency**: Reduces total storage needs while maintaining data quality

### Controllers, Services, and Schemas

The application logic is separated into several layers:

1. **Controllers** (`currency_controller.py`, `exchange_rate_controller.py`):
   - Implement the business logic for reading from the DB, caching results, etc.
   - Coordinate between the API layer and data access layer
   - Handle caching strategies and database interactions

2. **Schemas** (`schema.py`):
   - Define the Pydantic models used for validation and JSON response structures
   - Ensure type safety and validation of inputs/outputs
   - Provide serialization/deserialization of data

3. **Routes** (`route.py`):
   - Define the FastAPI endpoints that tie everything together
   - Map HTTP methods to controller functions
   - Handle request validation and response formatting

### Celery Tasks and Scheduling

Koel uses Celery for background task processing and scheduling:

1. **Celery Worker**:
   - Runs tasks in the background for scraping
   - Handles retrying failed tasks
   - Processes the ETL pipeline asynchronously

2. **Celery Beat**:
   - Schedules scraping intervals:
     - Every 6 hours for "primary" currencies (top ~15)
     - Every 12 hours for "secondary" currencies (remaining ~140)
   - Maintains consistent schedule for data freshness

3. **Task Implementation**:
   - The tasks themselves handle both multi-pair and single-pair fallback logic
   - Progress tracking and reporting is implemented
   - Error handling and retry logic is built in

```python
# Scheduled tasks for primary and secondary currencies
@celery_app.task(bind=True, max_retries=3)
def scrape_currency_group(self, group_type):
    """
    Task to scrape a specific group of currencies.

    Args:
        group_type: Type of currency group ('major', 'secondary', etc.)
    """
    ....

# Configure Celery Beat schedule
app.conf.beat_schedule = {
     # Primary currencies every 6 hours
    "scrape-primary-currencies-every-6-hours": {
        "task": "app.tasks.exchange_rates.scrape_currency_group",
        "schedule": crontab(hour="0,6,12,18", minute=0),
        "args": ["primary"],
    },
    
    # Secondary currencies every 12 hours
    "scrape-secondary-currencies-every-12-hours": {
        "task": "app.tasks.exchange_rates.scrape_currency_group",
        "schedule": crontab(hour="3,15", minute=0),
        "args": ["secondary"],
    },
    # Optionally, if you still want an overall full scrape at a time when group tasks are not running,
    # schedule it at an off-peak hour. Otherwise, you can remove it.
    # "scrape-all-currencies-daily": {
    #     "task": "app.tasks.exchange_rates.scrape_all_exchange_rates",
    #     "schedule": crontab(hour="21", minute="0"),
    # },
}
```

**Why Celery?**
1. **Asynchronous Execution**: Non-blocking background processing
2. **Scheduled Tasks**: Precise control over task scheduling
3. **Parallelism**: Can run multiple scraping tasks concurrently
4. **Monitoring**: Built-in tools for monitoring task execution
5. **Reliability**: Retry mechanisms and error handling

### API Implementation

The API is implemented using FastAPI with the following endpoints:

1. **GET /api/currencies**: List all available currencies
2. **GET /api/rates**: Get exchange rates with optional filtering
3. **GET /api/rates/history**: Get historical exchange rates

```python
@router.get("/rates", response_model=ApiResponse[ExchangeRateWithCurrencySchema])
async def get_exchange_rate(
    base: str,
    target: str,
    amount: Optional[Decimal] = None,
    db: Session = Depends(get_db),
):
    """Get the current exchange rate between two currencies with optional amount conversion."""
    result = ExchangeRateController.get_current_rate(db, base, target, amount)
    return success_response(
        data=result, message="Exchange rate retrieved successfully."
    )
```

**Why FastAPI?**
1. **Performance**: Built on Starlette and Pydantic for high performance
2. **Automatic Documentation**: OpenAPI and Swagger UI generation
3. **Type Safety**: Type hints and validation
4. **Async Support**: Native support for asynchronous operations
5. **Modern Features**: Dependency injection, path operations, etc.

## Performance Optimizations

### Database Indexes

Strategic indexes for the most common query patterns:

```sql
-- For quick lookups by currency code
CREATE INDEX currencies_index ON currencies(code);

-- In the exchange_rates table, we have a three-column index
-- covering (base_currency_id, target_currency_id, created_at).
-- This matches your Alembic migration file and ensures
-- quick lookups by base, target, and date/time.
CREATE INDEX exchange_rates_index ON exchange_rates (base_currency_id, target_currency_id, created_at);
```

**Why these indexes?**
1. **Query Performance**: Significantly speeds up the most frequent queries
2. **Covering Indexes**: Some indexes include all fields needed for certain queries
3. **Selective Indexing**: Focus on high-cardinality fields that benefit from indexing
4. **Balance**: Careful not to over-index, which can slow down writes

### Redis Caching Implementation

Koel uses Redis to cache frequently accessed data:

```python
@staticmethod
    def get_current_rate(
        db: Session, base_code: str, target_code: str, amount: Optional[Decimal] = None
    ) -> ExchangeRateWithCurrencySchema:
        """
        Get the most recent exchange rate between two currencies with optional amount conversion.
        """
        if base_code.upper() == target_code.upper():
            raise HTTPException(
                status_code=400, detail="Base and target currencies cannot be the same."
            )

        cache_key = f"exchange_rate:{base_code.upper()}-{target_code.upper()}"
        cached_data = CacheManager.get(cache_key)
        if cached_data:
            result = ExchangeRateWithCurrencySchema.model_validate(cached_data)
            if amount is not None:
                converted_amount = amount * Decimal(str(result.rate))
                rounded_amount = round(converted_amount, result.target_currency.decimal_digits)
                result.amount = amount
                result.converted_amount = rounded_amount
            return result

        logger.info(
            f"Fetching exchange rate for {base_code.upper()} to {target_code.upper()}"
        )

        # Get currency records
        base_currency = CurrencyController.get_currency_by_code(db, base_code)
        target_currency = CurrencyController.get_currency_by_code(db, target_code)

        # Query the most recent exchange rate
        exchange = (
            db.query(ExchangeRate)
            .filter(
                ExchangeRate.base_currency_id == base_currency.id,
                ExchangeRate.target_currency_id == target_currency.id,
            )
            .order_by(desc(ExchangeRate.created_at))
            .first()
        )
        if not exchange:
            raise HTTPException(status_code=404, detail="Exchange rate not found.")

        # Set related currencies to the exchange to avoid validation errors.
        exchange.base_currency = base_currency
        exchange.target_currency = target_currency

        result = ExchangeRateWithCurrencySchema.model_validate(exchange)

        # Add conversion information if an amount is provided.
        if amount is not None:
            converted_amount = amount * Decimal(str(result.rate))
            rounded_amount = round(converted_amount, target_currency.decimal_digits)
            result.amount = amount
            result.converted_amount = rounded_amount

        CacheManager.set(cache_key, result.dict(), expire=3600)
        return result

```

The caching strategy includes:
1. Cache exchange rates for a specific base-target pair
2. Cache currency lists and metadata
3. Cache TTLs based on usage patterns
4. Cache invalidation on new data scraping
5. Cache keys based on all query parameters

## Scaling Considerations

As the system grows, several scaling strategies are available:

### Database Scaling

1. **Vertical Scaling**:
   - Increase resources (CPU, RAM) for the database server
   - Optimize query execution plans
   - Tune PostgreSQL configuration

2. **Horizontal Scaling**:
   - PostgreSQL partitioning keeps queries fast
   - Potential to add read replicas for high API volume
   - If data grows beyond a single DB node, could shard by date range or currency

### Caching Strategies

1. **Redis Scaling**:
   - Redis cluster or distributed cache if usage grows
   - More advanced caching strategies (e.g., partial invalidation) if needed
   - Predictive pre-caching based on usage patterns

### Application Scaling

1. **Horizontal Scaling**:
   - Deploy multiple API instances behind a load balancer
   - Distribute Celery workers across multiple servers
   - Container orchestration with Kubernetes

2. **Functional Partitioning**:
   - Separate read and write operations (CQRS pattern)
   - Create specialized services for different functions

**Why these considerations?**
1. **Predictable Growth**: Exchange rate data volume grows at a predictable rate
2. **Read-Heavy Workload**: Most operations are reads, which scale more easily
3. **Cost Efficiency**: Different scaling strategies for different components
4. **Future-Proofing**: Architecture designed to accommodate growth

## Deployment

The application is containerized using Docker and orchestrated with Docker Compose:

```yaml
# docker-compose.yml
version: '3.8'

services:
  api:
    build: .
    ports:
      - "8000:8000"
    depends_on:
      - postgres
      - redis
      - celery-worker
    environment:
      - DATABASE_URL=postgresql://koel:koel@postgres:5432/koel
      - REDIS_URL=redis://redis:6379/0
    volumes:
      - ./logs:/app/logs

  postgres:
    image: postgres:14
    ports:
      - "5432:5432"
    environment:
      - POSTGRES_USER=koel
      - POSTGRES_PASSWORD=koel
      - POSTGRES_DB=koel
    volumes:
      - postgres-data:/var/lib/postgresql/data

  redis:
    image: redis:6
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data

  celery-worker:
    build: .
    command: celery -A app.tasks.celery_app worker --loglevel=info
    depends_on:
      - postgres
      - redis
    environment:
      - DATABASE_URL=postgresql://koel:koel@postgres:5432/koel
      - REDIS_URL=redis://redis:6379/0
    volumes:
      - ./logs:/app/logs

  celery-beat:
    build: .
    command: celery -A app.tasks.celery_app beat --loglevel=info
    depends_on:
      - postgres
      - redis
      - celery-worker
    environment:
      - DATABASE_URL=postgresql://koel:koel@postgres:5432/koel
      - REDIS_URL=redis://redis:6379/0
    volumes:
      - ./logs:/app/logs

volumes:
  postgres-data:
  redis-data:
```

**Why Docker?**
1. **Consistency**: Ensures the same environment across development and production
2. **Isolation**: Each component runs in its own container
3. **Scalability**: Easy to scale individual components
4. **Portability**: Can be deployed on any system supporting Docker
5. **Resource Efficiency**: Fine-grained control over resource allocation

## Monitoring and Logging

The application uses a custom logging module to track operations and errors:

```python
import logging
import os
from logging.handlers import RotatingFileHandler
from typing import Optional
from datetime import datetime
import slack_sdk
import threading
from functools import lru_cache
from pathlib import Path

class CustomLogger:
    _instance = None
    _lock = threading.Lock()
    _initialized = False

    def __new__(cls, *args, **kwargs):
        """Singleton pattern to ensure one logger instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(CustomLogger, cls).__new__(cls)
        return cls._instance

    def __init__(
        self,
        app_name: str = "app",
        log_level: str = "INFO",
        log_dir: str = "logs",
        log_file_name: str = "app.log",
        slack_webhook: Optional[str] = None,
        max_file_size: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5
    ):
        if self._initialized:
            return

        self.app_name = app_name
        self.log_level = getattr(logging, log_level.upper(), logging.INFO)
        self.log_dir = Path(log_dir)
        self.log_file_name = log_file_name
        self.slack_webhook = slack_webhook
        self.max_file_size = max_file_size
        self.backup_count = backup_count
        self.slack_client = slack_sdk.WebClient() if slack_webhook else None

        # Create logs directory
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Initialize logger
        self.logger = logging.getLogger(self.app_name)
        self.logger.setLevel(self.log_level)

        # Clear any existing handlers
        self.logger.handlers = []

        # Setup handlers
        self._setup_console_handler()
        self._setup_file_handler()
        if self.slack_webhook:
            self._setup_slack_handler()

        self._initialized = True

    def _setup_console_handler(self):
        """Configure console output with colored formatting."""
        console_handler = logging.StreamHandler()
        console_handler.setLevel(self.log_level)
        
        class ColoredFormatter(logging.Formatter):
            COLORS = {
                'DEBUG': '\033[94m',    # Blue
                'INFO': '\033[92m',     # Green
                'WARNING': '\033[93m',  # Yellow
                'ERROR': '\033[91m',    # Red
                'CRITICAL': '\033[95m', # Magenta
                'RESET': '\033[0m'
            }

            def format(self, record):
                level = record.levelname
                color = self.COLORS.get(level, '')
                message = super().format(record)
                return f"{color}{message}{self.COLORS['RESET']}"

        console_formatter = ColoredFormatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)

    def _setup_file_handler(self):
        """Configure rotating file handler with a single fixed log file."""
        log_file = self.log_dir / self.log_file_name
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=self.max_file_size,
            backupCount=self.backup_count
        )
        file_handler.setLevel(self.log_level)
        
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s - [%(filename)s:%(lineno)d]',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)

    def _setup_slack_handler(self):
        """Configure Slack handler for ERROR and CRITICAL logs."""
        class SlackHandler(logging.Handler):
            def __init__(self, logger_instance):
                super().__init__()
                self.logger_instance = logger_instance
                self.setLevel(logging.ERROR)

            def emit(self, record):
                try:
                    msg = self.format(record)
                    self.logger_instance._send_to_slack({
                        "text": f"*{record.levelname}* in *{self.logger_instance.app_name}*\n"
                                f"```{msg}```\n"
                                f"File: {record.filename}:{record.lineno}"
                    })
                except Exception as e:
                    print(f"Failed to send Slack message: {e}")

        slack_handler = SlackHandler(self)
        slack_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        slack_handler.setFormatter(slack_formatter)
        self.logger.addHandler(slack_handler)

    @lru_cache(maxsize=100)
    def _send_to_slack(self, message: dict):
        """Send message to Slack with caching to prevent duplicate messages."""
        if self.slack_client:
            try:
                self.slack_client.chat_postMessage(
                    channel="#logs",
                    **message
                )
            except Exception as e:
                print(f"Slack notification failed: {e}")

    def __getattr__(self, name):
        """
        Delegate logging methods (debug, info, warning, error, critical, exception) to the underlying logger.
        This ensures the caller's file and line number are captured correctly.
        """
        return getattr(self.logger, name)


def get_logger(
    app_name: str = "app",
    log_level: str = "INFO",
    log_dir: str = "logs",
    log_file_name: str = "app.log",
    slack_webhook: Optional[str] = None
) -> CustomLogger:
    """Factory function to get or create a logger instance."""
    return CustomLogger(
        app_name=app_name,
        log_level=log_level,
        log_dir=log_dir,
        log_file_name=log_file_name,
        slack_webhook=slack_webhook
    )
```

**Why this logging approach?**
1. **Separation**: Different log files for different components
2. **Rotation**: Prevents log files from growing too large
3. **Comprehensive**: Captures both console and file output
4. **Structured**: Consistent format for easy parsing
5. **Configurable**: Log levels can be adjusted based on environment
6. **Alerting**: Slack notifications for critical errors
7. **Thread-Safe**: Singleton pattern ensures only one logger instance

## Future Enhancements

Potential future improvements:

1. **Machine Learning Integration**: 
   - Anomaly detection for exchange rate fluctuations
   - Prediction of scraper failures
   - Optimization of scraping schedules

2. **Advanced Caching**:
   - Predictive pre-caching based on usage patterns
   - Multi-level cache with different TTLs
   - Cache warming strategies

3. **Enhanced Reliability**:
   - Geographic distribution of scrapers
   - Alternative data sources (paid APIs as fallback)
   - Real-time monitoring and alerting

4. **Additional Features**:
   - Historical trend analysis
   - Rate change notifications
   - Custom base currency baskets

**Why these enhancements?**
1. **Value Addition**: Provides more than just raw exchange rates
2. **Competitive Edge**: Differentiates from other exchange rate APIs
3. **Robustness**: Further improves reliability and accuracy
4. **User Needs**: Addresses advanced use cases