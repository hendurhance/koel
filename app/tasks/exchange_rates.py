import time
from app.utils.custom_logger import get_logger
from datetime import datetime
from typing import Dict, List
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.dialects.postgresql import insert
from app.db.database import get_db
from app.models.models import Currency, ExchangeRate
from app.exceptions import ScrapingException
from app.tasks.celery_app import celery_app
from app.scraping.manager import ScraperManager
from app.exceptions import ScrapingException
from app.scraping.manager import ScraperCapability
from app.tasks.progress_tracker import ProgressTracker

logger = get_logger(__name__)


@celery_app.task(bind=True, max_retries=3)
def scrape_all_exchange_rates(self):
    """
    Main task to scrape exchange rates for all currency pairs.
    Uses a failsafe mechanism to try different sources.
    """

    job_id = f"scrape_rates_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    ProgressTracker.start_job(job_id)

    start_time = time.time()
    logger.info(f"Starting exchange rate scraping task {job_id} at {datetime.now()}")

    # Get all currencies from the database
    db = next(get_db())

    try:
        # Get all currencies from the database
        currencies = db.query(Currency).all()
        if not currencies:
            logger.error("No currencies found in the database.")
            ProgressTracker.complete_job(job_id, "failed")
            return {"status": "failed", "message": "No currencies found"}

        # Create scraper manager
        scraper_manager = ScraperManager()

        # Track all successful and failed pairs
        successful_pairs = 0
        failed_pairs = 0
        all_rates = []

        for base_currency in currencies:
            try:
                success = False
                result = None

                # Try multi-pair scrapers first
                try:
                    # Use the scraper manager to get rates with failsafe (only multi-pair)
                    result = scrape_with_multi_pair(
                        scraper_manager=scraper_manager,
                        base_currency=base_currency.code,
                        base_name=base_currency.name,
                        base_name_plural=base_currency.name_plural,
                    )

                    success = True

                except ScrapingException as e:
                    logger.error(
                        f"Failed to scrape from all multi-pair sources for {base_currency.code}: {e}"
                    )

                # If multi-pair scrapers failed, try single-pair scrapers
                if not success:
                    combined_rates = {}
                    source_used = None
                    now = datetime.now()

                    for target_currency in currencies:
                        # Skip self-conversion
                        if target_currency.id == base_currency.id:
                            continue
                        try:
                            # Use the scraper manager to get rates with failsafe (only single-pair)
                            result = scrape_with_single_pair(
                                scraper_manager=scraper_manager,
                                base_currency=base_currency.code,
                                target_currency=target_currency.code,
                                base_name=base_currency.name,
                                base_name_plural=base_currency.name_plural,
                            )
                            combined_rates.update(result["rates"])
                            # Track which source was used (use the first successful one)
                            if not source_used:
                                source_used = result["source"]

                        except ScrapingException as e:
                            logger.error(
                                f"Failed to scrape from all single-pair sources for {base_currency.code} to {target_currency.code}: {e}"
                            )
                            failed_pairs += 1
                            continue

                    # If we got any rates, consider it a success
                    if combined_rates:
                        result = {
                            "rates": combined_rates,
                            "source": source_used or "combined",
                            "timestamp": datetime.now(),
                        }
                        success = True
                # If we got results, process them
                if success and result:
                    rates = result["rates"]
                    source = result["source"]
                    now = datetime.now()  # Ensure 'now' is defined regardless of which path was taken

                    for target_currency in currencies:
                        # Skip self-conversion
                        if target_currency.id == base_currency.id:
                            continue

                        # Check if the rate exists in the scraped data
                        if target_currency.code in rates:
                            rate = rates[target_currency.code]
                            all_rates.append(
                                {
                                    "base_currency_id": base_currency.id,
                                    "target_currency_id": target_currency.id,
                                    "rate": rate,
                                    "source": source,
                                    "created_at": now,
                                }
                            )
                            successful_pairs += 1
                        else:
                            logger.warning(
                                f"Rate for {base_currency.code} to {target_currency.code} not found in scraped data"
                            )
                            failed_pairs += 1
                    # Mark this currency as complete
                    ProgressTracker.mark_currency_complete(job_id, base_currency.code)
                else:
                    logger.error(
                        f"Failed to scrape rates for {base_currency.code} from all sources"
                    )
                    failed_pairs += len(currencies) - 1
                    ProgressTracker.mark_currency_failed(job_id, base_currency.code)

                    # Schedule a retry for this currency if needed
                    if ProgressTracker.should_retry_currency(
                        job_id, base_currency.code
                    ):
                        scrape_single_currency.apply_async(
                            args=[base_currency.id],
                            countdown=60 * 5,  # Retry after 5 minutes
                        )
            except Exception as e:
                logger.error(f"Scraping failed for {base_currency.code}: {e}")
                failed_pairs += len(currencies) - 1  # All target currencies failed
                ProgressTracker.mark_currency_failed(job_id, base_currency.code)

                # Schedule a retry for this currency if needed
                if ProgressTracker.should_retry_currency(job_id, base_currency.code):
                    scrape_single_currency.apply_async(
                        args=[base_currency.id],
                        countdown=60 * 5,  # Retry after 5 minutes
                    )

        # Bulk insert all rates into the database
        if all_rates:
            bulk_insert_rates(db, all_rates)

        execution_time = time.time() - start_time
        logger.info(
            f"Completed exchange rate scraping task in {execution_time:.2f} seconds. "
            f"Successful: {successful_pairs}, Failed: {failed_pairs}"
        )
        ProgressTracker.complete_job(job_id)

        return {
            "status": "success",
            "message": f"Scraped {successful_pairs} pairs successfully in {execution_time:.2f} seconds",
            "failed": failed_pairs,
            "job_id": job_id,
        }

    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error: {e}")
        ProgressTracker.complete_job(job_id, "failed")
        return {"status": "failed", "message": str(e)}
    except Exception as e:
        logger.error(f"Error in exchange rate scraping task: {e}")
        ProgressTracker.complete_job(job_id, "failed")
        self.retry(exc=e, countdown=60 * 5)  # Retry after 5 minutes
        return {"status": "failed", "message": str(e)}
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3)
def scrape_single_currency(self, currency_id):
    """
    Retry task for a single currency that failed during the main scraping task.
    Only processes one base currency against all target currencies.

    Args:
        currency_id: ID of the base currency to scrape
    """
    logger.info(f"Starting single currency retry task for currency ID {currency_id}")

    # Get a database session
    db = next(get_db())

    try:
        # Get the base currency and all target currencies
        base_currency = db.query(Currency).filter(Currency.id == currency_id).first()
        if not base_currency:
            logger.error(f"Base currency with ID {currency_id} not found")
            return {
                "status": "failed",
                "message": f"Currency with ID {currency_id} not found",
            }

        # Store the necessary values before closing the session or in case of detachment
        base_currency_code = base_currency.code
        base_currency_name = base_currency.name
        base_currency_name_plural = base_currency.name_plural
        base_currency_id = base_currency.id

        all_currencies = db.query(Currency).all()
        # Create a mapping of currency IDs to their codes for later reference
        currency_mapping = {c.id: {"code": c.code, "id": c.id} for c in all_currencies}

        # Create a scraper manager
        scraper_manager = ScraperManager()

        try:
            # Track results across multiple sources
            current_rates = []
            now = datetime.now()  # Define 'now' at the beginning for use in any path
            source_used = None

            # First try multi-pair scrapers
            try:
                # Use the multi-pair scrapers first
                result = scrape_with_multi_pair(
                    scraper_manager=scraper_manager,
                    base_currency=base_currency_code,
                    base_name=base_currency_name,
                    base_name_plural=base_currency_name_plural,
                )

                rates = result["rates"]
                source = result["source"]

                # Process the rates
                for target_id, target_info in currency_mapping.items():
                    # Skip self-conversion
                    if target_id == base_currency_id:
                        continue

                    # Check if the rate exists in the scraped data
                    target_code = target_info["code"]
                    if target_code in rates:
                        rate = rates[target_code]
                        current_rates.append(
                            {
                                "base_currency_id": base_currency_id,
                                "target_currency_id": target_id,
                                "rate": rate,
                                "source": source,
                                "created_at": now,
                            }
                        )

            except ScrapingException:
                # If multi-pair scrapers fail, try single-pair for each target currency
                for target_id, target_info in currency_mapping.items():
                    # Skip self-conversion
                    if target_id == base_currency_id:
                        continue

                    target_code = target_info["code"]

                    try:
                        result = scrape_with_single_pair(
                            scraper_manager=scraper_manager,
                            base_currency=base_currency_code,
                            target_currency=target_code,
                            base_name=base_currency_name,
                            base_name_plural=base_currency_name_plural,
                        )

                        rates = result["rates"]
                        source = result["source"]

                        # Use the first successful source for all
                        if not source_used:
                            source_used = source

                        # Get the rate for this specific target currency
                        if target_code in rates:
                            rate = rates[target_code]
                            current_rates.append(
                                {
                                    "base_currency_id": base_currency_id,
                                    "target_currency_id": target_id,
                                    "rate": rate,
                                    "source": source_used
                                    or source,  # Use consistent source
                                    "created_at": now,
                                }
                            )
                    except ScrapingException:
                        # Skip this target currency and continue with others
                        logger.warning(
                            f"Failed to scrape rate for {base_currency_code} to {target_code}"
                        )
                        continue

            # Bulk insert the rates
            if current_rates:
                try:
                    # Call bulk_insert_rates but don't let it close our session
                    bulk_insert_rates_without_closing(db, current_rates)
                    db.commit()
                except Exception as e:
                    db.rollback()
                    logger.error(f"Error inserting rates: {e}")
                    raise

            logger.info(
                f"Successfully scraped {len(current_rates)} rates for {base_currency_code}"
            )
            return {
                "status": "success",
                "message": f"Scraped {len(current_rates)} rates for {base_currency_code}",
            }

        except Exception as e:
            logger.error(f"All sources failed for {base_currency_code}: {e}")
            self.retry(
                exc=e, countdown=60 * 15
            )  # Retry after 15 minutes with exponential backoff
            return {"status": "failed", "message": str(e)}

    except Exception as e:
        logger.error(f"Error in single currency scraping task: {e}")
        db.rollback()  # Added rollback for error handling
        self.retry(exc=e, countdown=60 * 5)  # Retry after 5 minutes
        return {"status": "failed", "message": str(e)}
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3)
def scrape_currency_group(self, group_type):
    """
    Task to scrape a specific group of currencies.

    Args:
        group_type: Type of currency group ('major', 'secondary', etc.)
    """
    logger.info(f"Starting scraping task for {group_type} currencies")

    # Define currency groups
    CURRENCY_GROUPS = {
        "primary": [
            "USD",  # US Dollar - Global reserve currency
            "EUR",  # Euro - Major currency for the Eurozone
            "GBP",  # British Pound Sterling - Historically significant
            "JPY",  # Japanese Yen - Major Asian currency, safe-haven status
            "CAD",  # Canadian Dollar - Commodity-linked, stable economy
            "AUD",  # Australian Dollar - Commodity-driven, widely traded
            "CHF",  # Swiss Franc - Safe-haven currency
            "CNY",  # Chinese Yuan - Growing global influence
            "SGD",  # Singapore Dollar - Strong, stable, regional hub
            "HKD",  # Hong Kong Dollar - Pegged to USD, financial center
            "KRW",  # South Korean Won - Major industrialized economy
            "SEK",  # Swedish Krona - Stable, widely traded in Europe
            "NOK",  # Norwegian Krone - Oil-linked, strong economy
            "NZD",  # New Zealand Dollar - Commodity-driven, stable
            "INR",  # Indian Rupee - Emerging market, large economy
        ],
        "secondary": [
            "AED",
            "AFN",
            "XCD",
            "ALL",
            "AMD",
            "AOA",
            "ARS",
            "AWG",
            "AZN",
            "BAM",
            "BBD",
            "BDT",
            "XOF",
            "BGN",
            "BHD",
            "BIF",
            "BMD",
            "BND",
            "BOB",
            "BRL",
            "BSD",
            "BTN",
            "BWP",
            "BYN",
            "BZD",
            "CDF",
            "XAF",
            "CLP",
            "COP",
            "CRC",
            "CUP",
            "CVE",
            "ANG",
            "CZK",
            "DJF",
            "DKK",
            "DOP",
            "DZD",
            "EGP",
            "MAD",
            "ERN",
            "ETB",
            "FJD",
            "FKP",
            "GEL",
            "GHS",
            "GIP",
            "GMD",
            "GNF",
            "GTQ",
            "GYD",
            "HNL",
            "HRK",
            "HTG",
            "HUF",
            "IDR",
            "ILS",
            "IQD",
            "IRR",
            "ISK",
            "JMD",
            "JOD",
            "KES",
            "KGS",
            "KHR",
            "KMF",
            "KPW",
            "KWD",
            "KYD",
            "KZT",
            "LAK",
            "LBP",
            "LKR",
            "LRD",
            "LSL",
            "LYD",
            "MDL",
            "MGA",
            "MKD",
            "MMK",
            "MNT",
            "MOP",
            "MRO",
            "MUR",
            "MVR",
            "MWK",
            "MXN",
            "MYR",
            "MZN",
            "NAD",
            "XPF",
            "NGN",
            "NIO",
            "NPR",
            "OMR",
            "PAB",
            "PEN",
            "PGK",
            "PHP",
            "PKR",
            "PLN",
            "PYG",
            "QAR",
            "RON",
            "RSD",
            "RUB",
            "RWF",
            "SAR",
            "SBD",
            "SCR",
            "SDG",
            "SHP",
            "SLL",
            "SOS",
            "SRD",
            "SSP",
            "STD",
            "SYP",
            "SZL",
            "THB",
            "TJS",
            "TMT",
            "TND",
            "TOP",
            "TRY",
            "TTD",
            "TWD",
            "TZS",
            "UAH",
            "UGX",
            "UYU",
            "UZS",
            "VEF",
            "VND",
            "VUV",
            "WST",
            "YER",
            "ZMW",
            "ZWL",
            "MRU",
            "STN",
        ],
    }

    if group_type not in CURRENCY_GROUPS:
        logger.error(f"Unknown currency group: {group_type}")
        return {"status": "failed", "message": f"Unknown currency group: {group_type}"}

    job_id = f"scrape_{group_type}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    ProgressTracker.start_job(job_id)

    # Get a database session
    db = next(get_db())

    try:
        # Get currencies for this group
        group_codes = CURRENCY_GROUPS[group_type]
        currencies = db.query(Currency).filter(Currency.code.in_(group_codes)).all()

        if not currencies:
            logger.error(f"No currencies found for group {group_type}")
            ProgressTracker.complete_job(job_id, "failed")
            return {
                "status": "failed",
                "message": f"No currencies found for group {group_type}",
            }

        # Get all target currencies
        all_currencies = db.query(Currency).all()

        # Create a scraper manager
        scraper_manager = ScraperManager()

        # Track results
        successful_pairs = 0
        failed_pairs = 0
        all_rates = []
        now = datetime.now()

        # Process each base currency
        for base_currency in currencies:
            try:
                # Use the scraper manager to get rates with failsafe
                result = scrape_with_multi_pair(
                    scraper_manager=scraper_manager,
                    base_currency=base_currency.code,
                    base_name=base_currency.name,
                    base_name_plural=base_currency.name_plural,
                )

                rates = result["rates"]
                source = result["source"]

                # Create exchange rate records
                for target_currency in all_currencies:
                    # Skip self-conversion
                    if target_currency.id == base_currency.id:
                        continue

                    # Check if the rate exists in the scraped data
                    if target_currency.code in rates:
                        rate = rates[target_currency.code]
                        all_rates.append(
                            {
                                "base_currency_id": base_currency.id,
                                "target_currency_id": target_currency.id,
                                "rate": rate,
                                "source": source,
                                "created_at": now,
                            }
                        )
                        successful_pairs += 1
                    else:
                        failed_pairs += 1

                # Mark this currency as complete
                ProgressTracker.mark_currency_complete(job_id, base_currency.code)

            except ScrapingException:
                # If multi-pair scrapers fail, try single-pair for each target
                combined_success = False
                source_used = None

                for target_currency in all_currencies:
                    # Skip self-conversion
                    if target_currency.id == base_currency.id:
                        continue

                    try:
                        result = scrape_with_single_pair(
                            scraper_manager=scraper_manager,
                            base_currency=base_currency.code,
                            target_currency=target_currency.code,
                            base_name=base_currency.name,
                            base_name_plural=base_currency.name_plural,
                        )

                        rates = result["rates"]
                        source = result["source"]

                        # Use the first successful source for all
                        if not source_used:
                            source_used = source

                        # Get the rate for this specific target currency
                        if target_currency.code in rates:
                            rate = rates[target_currency.code]
                            all_rates.append(
                                {
                                    "base_currency_id": base_currency.id,
                                    "target_currency_id": target_currency.id,
                                    "rate": rate,
                                    "source": source_used
                                    or source,
                                    "created_at": now,
                                }
                            )
                            successful_pairs += 1
                            combined_success = True
                        else:
                            failed_pairs += 1
                    except ScrapingException:
                        failed_pairs += 1
                        continue

                # Mark the currency complete if we had any success
                if combined_success:
                    ProgressTracker.mark_currency_complete(job_id, base_currency.code)
                else:
                    ProgressTracker.mark_currency_failed(job_id, base_currency.code)
                    failed_pairs += (
                        len(all_currencies) - 1
                    )  # All target currencies failed
                # Schedule a retry for this currency if needed
                if ProgressTracker.should_retry_currency(job_id, base_currency.code):
                    scrape_single_currency.apply_async(
                        args=[base_currency.id],
                        countdown=60 * 5,  # Retry after 5 minutes
                    )
            except Exception as e:
                logger.error(f"Scraping failed for {base_currency.code}: {e}")
                failed_pairs += len(all_currencies) - 1
                ProgressTracker.mark_currency_failed(job_id, base_currency.code)
                # Schedule a retry for this currency if needed
                if ProgressTracker.should_retry_currency(job_id, base_currency.code):
                    scrape_single_currency.apply_async(
                        args=[base_currency.id],
                        countdown=60 * 5,  # Retry after 5 minutes
                    )
        # If we have any rates, bulk insert them
        if all_rates:
            try:
                bulk_insert_rates_without_closing(db, all_rates)
                db.commit()
            except Exception as e:
                db.rollback()
                logger.error(f"Error inserting rates: {e}")
                raise

        ProgressTracker.complete_job(job_id)

        logger.info(
            f"Completed {group_type} currency scraping task. "
            f"Successful: {successful_pairs}, Failed: {failed_pairs}"
        )

        return {
            "status": "success",
            "message": f"Scraped {successful_pairs} pairs successfully for {group_type} currencies",
            "failed": failed_pairs,
            "job_id": job_id,
        }

    except Exception as e:
        logger.error(f"Error in {group_type} currency scraping task: {e}")
        db.rollback()
        ProgressTracker.complete_job(job_id, "failed")
        self.retry(exc=e, countdown=60 * 5)  # Retry after 5 minutes
        return {"status": "failed", "message": str(e)}
    finally:
        db.close()


def bulk_insert_rates(db, rates: List[Dict]):
    """
    Bulk insert exchange rates into the database using the appropriate partition model.
    This function closes the database session.

    Args:
        db: Database session
        rates: List of rate dictionaries
    """
    try:
        if rates:
            stmt = insert(ExchangeRate).values(rates)

            # Handle conflicts - update rate and source if the record already exists
            stmt = stmt.on_conflict_do_update(
                constraint=f"unique_{ExchangeRate.__tablename__}",
                set_=dict(rate=stmt.excluded.rate, source=stmt.excluded.source),
            )

            db.execute(stmt)
            db.commit()
            logger.info(
                f"Bulk inserted {len(rates)} exchange rates into {ExchangeRate.__tablename__}"
            )
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Failed to bulk insert exchange rates: {e}")
        raise ScrapingException(f"Database error: {e}")
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error during bulk insert: {e}")
        raise ScrapingException(f"Unexpected error: {e}")
    finally:
        db.close()
        logger.info("Database session closed after bulk insert")


def bulk_insert_rates_without_closing(db, rates: List[Dict]):
    """
    Bulk insert exchange rates into the database without closing the session.
    This version does not commit or close the session, allowing the caller to do that.

    Args:
        db: Database session
        rates: List of rate dictionaries
    """
    try:
        if rates:
            stmt = insert(ExchangeRate).values(rates)

            # Handle conflicts - update rate and source if the record already exists
            stmt = stmt.on_conflict_do_update(
                constraint=f"unique_{ExchangeRate.__tablename__}",
                set_=dict(rate=stmt.excluded.rate, source=stmt.excluded.source),
            )

            db.execute(stmt)
            logger.info(
                f"Bulk inserted {len(rates)} exchange rates into {ExchangeRate.__tablename__}"
            )
    except SQLAlchemyError as e:
        logger.error(f"Failed to bulk insert exchange rates: {e}")
        raise ScrapingException(f"Database error: {e}")
    except Exception as e:
        logger.error(f"Unexpected error during bulk insert: {e}")
        raise ScrapingException(f"Unexpected error: {e}")


def scrape_with_multi_pair(
    scraper_manager, base_currency, base_name=None, base_name_plural=None
):
    """
    Try to scrape using multi-pair scrapers only.

    Returns:
        Dict containing rates and source info

    Raises:
        ScrapingException: If all multi-pair sources fail
    """
    errors = []

    for source_name in scraper_manager.source_priority:
        if source_name not in scraper_manager.sources:
            continue

        source = scraper_manager.sources[source_name]

        # Skip single-pair sources
        if source.capability != ScraperCapability.MULTI_PAIR:
            continue

        # Skip sources that need special parameters if we don't have them
        if (source.needs_base_name and not base_name) or (
            source.needs_base_plural and not base_name_plural
        ):
            continue

        try:
            scraper_params = {"base_currency": base_currency}

            if source.needs_base_name:
                scraper_params["base_name"] = base_name
            if source.needs_base_plural:
                scraper_params["base_name_plural"] = base_name_plural

            scraper = source.scraper_cls(**scraper_params)
            raw_data = scraper.extract()
            rates = scraper.transform(raw_data)

            if not rates:
                error_msg = f"Source {source_name} returned empty rates, considering as failure"
                logger.warning(error_msg)
                errors.append(error_msg)
                continue

            return {
                "rates": rates,
                "source": source_name,
                "timestamp": datetime.now(),
            }
        except Exception as e:
            error_msg = f"Failed to scrape from {source_name}: {str(e)}"
            logger.warning(error_msg)
            errors.append(error_msg)

    # If we get here, all multi-pair sources failed
    error_details = "\n".join(errors)
    raise ScrapingException(
        f"All multi-pair sources failed for base currency {base_currency}. Details:\n{error_details}"
    )


def scrape_with_single_pair(
    scraper_manager,
    base_currency,
    target_currency,
    base_name=None,
    base_name_plural=None,
):
    """
    Try to scrape a single currency pair using single-pair scrapers.

    Returns:
        Dict containing rates and source info

    Raises:
        ScrapingException: If all single-pair sources fail
    """
    errors = []

    for source_name in scraper_manager.source_priority:
        if source_name not in scraper_manager.sources:
            continue

        source = scraper_manager.sources[source_name]

        # Skip multi-pair sources
        if source.capability != ScraperCapability.SINGLE_PAIR:
            continue

        # Skip sources that need special parameters if we don't have them
        if (source.needs_base_name and not base_name) or (
            source.needs_base_plural and not base_name_plural
        ):
            continue

        try:
            scraper_params = {
                "base_currency": base_currency,
                "target_currency": target_currency,
            }

            if source.needs_base_name:
                scraper_params["base_name"] = base_name
            if source.needs_base_plural:
                scraper_params["base_name_plural"] = base_name_plural

            scraper = source.scraper_cls(**scraper_params)
            raw_data = scraper.extract()
            rates = scraper.transform(raw_data)

            if not rates:
                error_msg = f"Source {source_name} returned empty rates, considering as failure"
                logger.warning(error_msg)
                errors.append(error_msg)
                continue

            if target_currency not in rates:
                error_msg = f"Source {source_name} did not return rate for target currency {target_currency}"
                logger.warning(error_msg)
                errors.append(error_msg)
                continue

            return {
                "rates": rates,
                "source": source_name,
                "timestamp": datetime.now(),
            }
        except Exception as e:
            error_msg = f"Failed to scrape from {source_name}: {str(e)}"
            logger.warning(error_msg)
            errors.append(error_msg)

    # If we get here, all single-pair sources failed
    error_details = "\n".join(errors)
    raise ScrapingException(
        f"All single-pair sources failed for pair {base_currency}-{target_currency}. Details:\n{error_details}"
    )