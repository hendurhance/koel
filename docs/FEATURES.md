# Koel – Features

Koel is a self-hosted, event-driven currency exchange solution that provides robust scraping, caching, partitioned storage, and a REST API for real-time conversion. Below is an overview of its key features:

---

## 1. Self-Hosted & Unlimited Usage

- **No API Keys**: Eliminate the hassles of requesting API credentials or worrying about monthly quotas.  
- **No Usage Limits**: Host the app on your infrastructure; scale to accommodate all your traffic and data needs.  

---

## 2. Multiple Data Sources

- **Failover Mechanism**: If one source fails (rate-limited, server down), Koel automatically tries the next source.  
- **Factory Pattern**: Easily add or remove scraping sources without changing core logic—just implement a new `BaseScraper` subclass and register it.  
- **Single-Pair & Multi-Pair**: Scrapers can grab either a single exchange rate pair or a full matrix of rates at once.

---

## 3. Event-Driven Architecture

- **Celery Beat**: Schedules recurring scraping tasks at configured intervals (e.g., every 6 or 12 hours).  
- **Async Execution**: Celery workers handle all scraping and data processing in the background, ensuring the API remains responsive to user requests.

---

## 4. Partitioned Database

- **PostgreSQL Partitioning**: Large `exchange_rates` table is automatically partitioned by month to maintain efficient reads and writes.  
- **Scalability**: Partitioning ensures performance remains high as data grows exponentially.  
- **Easy Maintenance**: Old partitions can be archived or dropped without impacting current query performance.

---

## 5. Robust Caching

- **Redis Integration**: Frequently requested data—such as currency metadata or the latest exchange rates—is cached to reduce load on the database.  
- **Configurable TTL**: You can control how long caches last to balance freshness and performance.  
- **Progress Tracking**: Uses Redis to track Celery job statuses and retry counts (if a particular currency fails scraping).

---

## 6. Rate Limiting & User-Agent Rotation

- **Configurable Throttle**: Prevent hammering external sites by delaying requests. Defaults to around 50 requests per minute.  
- **Randomized User-Agents**: Cycle through a list of user-agent strings to avoid IP or bot detection.

---

## 7. Detailed Logging & Monitoring

- **Custom Logger**: Outputs to rotating files and optionally Slack, notifying you on errors or critical events.  
- **Log Levels**: Manage log granularity (DEBUG, INFO, WARNING, ERROR, CRITICAL) to suit your environment.

---

## 8. Extensible & Maintainable Codebase

- **Modular Architecture**: Clear separation of concerns (scraping, tasks, controllers, and schemas).  
- **Pydantic Schemas**: Enforces strict data validation for incoming and outgoing API data.  
- **Alembic Migrations**: Keep your database schema versioned and consistent.  

---

## 9. Dockerized Deployment

- **Dockerfile & docker-compose**: Build and run Koel in a container for easy setup and consistent environments.  
- **Scalability**: Spin up more Celery workers or additional API instances under load.

---

## 10. Use Cases

- **Production-ready**: Useful for startups or enterprises needing flexible, self-controlled exchange rate solutions.  
- **Backup / Fallback API**: Serve as a fallback if you rely on external APIs that could introduce usage limits or downtime.  
- **Data Analysis & Historical Records**: The partitioned database structure supports historical queries for trending and analytics.

---

**Koel** is designed to be a comprehensive, plug-and-play solution for all your currency exchange rate needs—robust, flexible, and easy to operate at scale.
