import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import json
from datetime import datetime
from app.db.database import SessionLocal
from app.models.models import Base, Currency

def seed_currencies():
    db = SessionLocal()
    try:
        current_dir = os.path.dirname(__file__)
        json_path = os.path.join(current_dir, 'currencies.json')
        with open(json_path, 'r', encoding='utf-8') as file:
            currencies_data = json.load(file)

            current_time = datetime.now()
            for currency_data in currencies_data:
                if not currency_data['name']:
                    continue

                existing_currency = db.query(Currency).filter(
                    Currency.code == currency_data['code']
                ).first()

                if not existing_currency:
                    currency = Currency(
                        name=currency_data['name'],
                        name_plural=currency_data['name_plural'],
                        code=currency_data['code'],
                        symbol=currency_data['symbol'],
                        decimal_digits=currency_data['decimal_digits'],
                        created_at=current_time,
                        updated_at=current_time
                    )
                    db.add(currency)

                db.commit()
                print("Currencies seeded successfully!")

    except Exception as e:
        db.rollback()
        print(f"Error seeding currencies: {str(e)}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_currencies()