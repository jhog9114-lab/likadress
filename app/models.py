from sqlalchemy import (
    Boolean,
    Column,
    Float,
    Integer,
    String,
    UniqueConstraint,
)

from app.database import Base


class Sale(Base):
    __tablename__ = "sales"

    srid = Column(String, primary_key=True)
    date = Column(String, index=True)
    last_change_date = Column(String)
    warehouse_name = Column(String)
    region_name = Column(String)
    nm_id = Column(Integer, index=True)
    supplier_article = Column(String)
    subject = Column(String)
    category = Column(String)
    brand = Column(String)
    tech_size = Column(String)
    barcode = Column(String)
    total_price = Column(Float)
    discount_percent = Column(Float)
    price_with_disc = Column(Float)
    finished_price = Column(Float)
    for_pay = Column(Float)
    is_return = Column(Boolean, default=False)


class Order(Base):
    __tablename__ = "orders"

    srid = Column(String, primary_key=True)
    date = Column(String, index=True)
    last_change_date = Column(String)
    warehouse_name = Column(String)
    region_name = Column(String)
    nm_id = Column(Integer, index=True)
    supplier_article = Column(String)
    subject = Column(String)
    category = Column(String)
    brand = Column(String)
    tech_size = Column(String)
    total_price = Column(Float)
    discount_percent = Column(Float)
    price_with_disc = Column(Float)
    is_cancel = Column(Boolean, default=False)
    cancel_date = Column(String)


class Stock(Base):
    __tablename__ = "stocks"
    __table_args__ = (
        UniqueConstraint("nm_id", "warehouse_name", "barcode", name="uq_stock_item"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    last_change_date = Column(String)
    warehouse_name = Column(String, index=True)
    nm_id = Column(Integer, index=True)
    supplier_article = Column(String)
    barcode = Column(String)
    subject = Column(String)
    category = Column(String)
    brand = Column(String)
    tech_size = Column(String)
    quantity = Column(Integer)
    in_way_to_client = Column(Integer)
    in_way_from_client = Column(Integer)
    quantity_full = Column(Integer)
    price = Column(Float)
    discount = Column(Float)


class Feedback(Base):
    __tablename__ = "feedbacks"

    id = Column(String, primary_key=True)
    nm_id = Column(Integer, index=True)
    product_name = Column(String)
    text = Column(String)
    pros = Column(String)
    cons = Column(String)
    rating = Column(Integer)
    created_date = Column(String, index=True)
    is_answered = Column(Boolean, default=False)
    answer_text = Column(String)


class Question(Base):
    __tablename__ = "questions"

    id = Column(String, primary_key=True)
    nm_id = Column(Integer, index=True)
    product_name = Column(String)
    text = Column(String)
    created_date = Column(String, index=True)
    is_answered = Column(Boolean, default=False)
    answer_text = Column(String)


class AdvertCampaign(Base):
    __tablename__ = "advert_campaigns"

    advert_id = Column(Integer, primary_key=True)
    name = Column(String)
    type_name = Column(String)
    status_name = Column(String)
    created_at = Column(String)
    start_time = Column(String)
    end_time = Column(String)


class AdvertStat(Base):
    __tablename__ = "advert_stats"
    __table_args__ = (
        UniqueConstraint("advert_id", "date", name="uq_advert_stat_day"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    advert_id = Column(Integer, index=True)
    date = Column(String, index=True)
    views = Column(Integer)
    clicks = Column(Integer)
    ctr = Column(Float)
    cpc = Column(Float)
    sum = Column(Float)
    atbs = Column(Integer)
    orders = Column(Integer)
    cr = Column(Float)
    orders_sum = Column(Float)
