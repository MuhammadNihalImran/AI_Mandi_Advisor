from sqlalchemy import Column, Integer, String, Float, Date

from app.db.database import Base


class MandiPrice(Base):
    """
    mandi_prices table – schema mirrors faisalabad_tomato_dataset.csv
    """

    __tablename__ = "mandi_prices"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    date = Column(Date, nullable=False, index=True)
    city = Column(String, nullable=False)
    crop = Column(String, nullable=False)

    # Weather
    temperature = Column(Float)   # ← temperature_c
    rainfall = Column(Float)      # ← rainfall_mm
    humidity = Column(Float)      # ← humidity_percent

    # Prices (PKR)
    price = Column(Float)         # ← avg_price_pkr
    min_price = Column(Float)     # ← min_price_pkr
    max_price = Column(Float)     # ← max_price_pkr
    price_spread = Column(Float)  # ← price_spread_pkr

    # Meta
    unit = Column(String)
    n_reports = Column(Integer)   # ← n_price_reports
    data_type = Column(String)
    source = Column(String)       # ← source_file
    latitude = Column(Float)
    longitude = Column(Float)
    weather_source = Column(String)

    def __repr__(self):
        return (
            f"<MandiPrice(id={self.id}, date={self.date}, "
            f"city='{self.city}', crop='{self.crop}', price={self.price})>"
        )
