from datetime import datetime, timezone, date, time
from uuid import UUID, uuid4
from app.database import Base
from pydantic import BaseModel
from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, String, Date, Numeric, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from decimal import Decimal

#UPDATE NEEDED.
# 1) PRICE IS HARD CODED, UPDATE DB TO DO THAT
def datetime_utcnow():
    return datetime.now(timezone.utc)

# The JSON body the browser sends to POST /chat.
class ChatRequest(BaseModel):
    conversation_id: str = None
    message: str

#convention [table name is lower clase and plural form of the entity] [class name is Singular form in Camel case]
class Conversation(Base):
    __tablename__ = "reservation_bot_conversations"

    id: Mapped[int] = mapped_column(primary_key=True)
    external_user_id: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(default=datetime_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime_utcnow, onupdate=datetime_utcnow
    )

    def __repr__(self):
        return f'Conversation({self.id}, "{self.external_user_id}", "{self.created_at}")'

class Message(Base):
    __tablename__ = "reservation_bot_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("reservation_bot_conversations.id"), index=True
    )
    role: Mapped[str] = mapped_column(String(10))
    content: Mapped[list | str] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(default=datetime_utcnow)

    def __repr__(self):
        return f'Message({self.id}, "{self.conversation_id}", "{self.role}", "{self.content}", "{self.created_at}")'

#combinaciones and detalle_combinaciones flattened into one table, one row per
#room in an option. combination_id is what groups a two room option together
class RoomCombinations(Base):
    __tablename__ = "room_combinations"

    id: Mapped[int] = mapped_column(primary_key=True)
    combination_type: Mapped[int] = mapped_column(index=True)
    hotel: Mapped[str] = mapped_column(String(50))
    adults: Mapped[int]
    kids: Mapped[int]
    total: Mapped[int]
    priority: Mapped[int]
    active: Mapped[bool]
    room_code: Mapped[str] = mapped_column(String(10), ForeignKey("room_types.room_code"))
    quantity: Mapped[int]

    room_type: Mapped["RoomTypes"] = relationship(back_populates="combinations")

    def __repr__(self):
        return f'RoomCombinations({self.id}, {self.combination_type}, "{self.hotel}", "{self.room_code}", adults={self.adults}, kids={self.kids}, quantity={self.quantity})'



class Allotments(Base):
    __tablename__ = "allotments"
    id: Mapped[int] = mapped_column(primary_key=True)
    #A or P, to match room_types, the mysql side stores 1 or 2
    hotel: Mapped[str] = mapped_column(String(50))
    room_code: Mapped[str] = mapped_column(String(10), ForeignKey("room_types.room_code"))
    check_in: Mapped[date]
    check_out: Mapped[date]
    availability: Mapped[str] = mapped_column(String(20))
    program: Mapped[str] = mapped_column(String(15))
    membership_number: Mapped[str] = mapped_column(String(7))
    quote: Mapped[int]
    online: Mapped[str] = mapped_column(String(2))
    synced_at: Mapped[datetime]

    room_type: Mapped["RoomTypes"] = relationship(back_populates="allotments")

    def __repr__(self):
        return f'Allotments({self.id}, "{self.hotel}", "{self.room_code}", "{self.check_in}", "{self.check_out}", "{self.availability}")'



class RoomTypes(Base):
    __tablename__ = "room_types"

    id: Mapped[int] = mapped_column(primary_key=True)
    hotel: Mapped[str] = mapped_column(String(50))
    room_code: Mapped[str] = mapped_column(String(10), unique=True)
    room_name: Mapped[str] = mapped_column(String(50))
    description: Mapped[str] = mapped_column(String(255))
    information: Mapped[str] = mapped_column(String(600))
    adults: Mapped[int]
    kids: Mapped[int]
    online: Mapped[str]
    max_allowance: Mapped[int]
    rates: Mapped[list["RoomRates"]] = relationship(back_populates="room_type")
    combinations: Mapped[list["RoomCombinations"]] = relationship(back_populates="room_type")
    allotments: Mapped[list["Allotments"]] = relationship(back_populates="room_type")

    def __repr__(self):
        return f'RoomTypes({self.id}, "{self.hotel}", "{self.room_code}", "{self.room_name}")'

class RoomRates(Base):
    __tablename__ = "room_rates"

    id: Mapped[int] = mapped_column(primary_key=True)
    room_code: Mapped[str] = mapped_column(String(10), ForeignKey("room_types.room_code"))
    time_of_the_week: Mapped[str] = mapped_column(String(10))
    points: Mapped[Decimal] = mapped_column(Numeric(6, 1))
    dollars: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    quetzales: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    year: Mapped[int]
    room_type: Mapped["RoomTypes"] = relationship(back_populates="rates")

    def __repr__(self):
        return f'RoomRates({self.id}, "{self.room_code}", "{self.time_of_the_week}", {self.points}, {self.dollars})'


class Calendar(Base):
    __tablename__ = "calendar"

    calendar_date: Mapped[date] = mapped_column("date", Date, primary_key=True)
    day: Mapped[str] = mapped_column(Text)
    time_of_the_week: Mapped[str] = mapped_column(Text)
    exchange_rate: Mapped[Decimal] = mapped_column(Numeric(8, 5))

    def __repr__(self):
        return f'Calendar("{self.calendar_date}", "{self.day}", "{self.time_of_the_week}", {self.exchange_rate})'


class Users(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(20), unique=True)
    full_name: Mapped[str] = mapped_column(String(64))
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20))
    department: Mapped[str] = mapped_column(String(20))
    office: Mapped[str] = mapped_column(String(20))
    is_active: Mapped[bool] = mapped_column(default=True)
    password_changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), onupdate=datetime_utcnow
    )

    def __repr__(self):
        return f'Users({self.id}, "{self.username}", "{self.full_name}", "{self.department}", "{self.office}")'


class Quotes(Base):
    __tablename__ = "quotes"

    id: Mapped[int] = mapped_column(primary_key=True)
    quote_number: Mapped[int] = mapped_column(Integer)
    membership_number: Mapped[str] = mapped_column(String(7))
    quoted_date: Mapped[date]
    quoted_time: Mapped[time]
    source: Mapped[str] = mapped_column(String(15))
    current_status: Mapped[str] = mapped_column(String(9))
    solicitor: Mapped[str] = mapped_column(String(40))
    result: Mapped[str] = mapped_column(String(16))
    points_category: Mapped[str] = mapped_column(String(15))
    available_points: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    available_bonus_points: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    guest_fee: Mapped[int]
    hotel: Mapped[str] = mapped_column(String(40))

    primary_account_holder: Mapped[str] = mapped_column(String(40))
    contract_number: Mapped[str] = mapped_column(String(7))
    available_points: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    available_bonus_points: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    created_by: Mapped[str] = mapped_column(String(20))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), onupdate=datetime_utcnow
    )
    updated_by: Mapped[str] = mapped_column(String(20))
    referred_by: Mapped[str] = mapped_column(String(8))


    def __repr__(self):
        return f'Quotes({self.id}, "{self.membership_number}", "{self.hotel}", "{self.quoted_date}", "{self.result}")'

class Points(Base):
    __tablename__ = "points"

    contract_number: Mapped[str] = mapped_column(String(7), ForeignKey("contracts.contract_number"), primary_key=True)
    points_per_contract: Mapped[int]
    points_paid_for: Mapped[Decimal] = mapped_column(Numeric(13, 1))
    points_used: Mapped[Decimal] = mapped_column(Numeric(13, 1))
    points_expired: Mapped[Decimal] = mapped_column(Numeric(13, 1))
    points_available: Mapped[Decimal] = mapped_column(Numeric(13, 1))
    bono_granted: Mapped[Decimal] = mapped_column(Numeric(13, 1))
    bono_used: Mapped[Decimal] = mapped_column(Numeric(13, 1))

    def __repr__(self):
        return f'Points("{self.contract_number}", available={self.points_available}, bono={self.bono_granted})'
class Contracts(Base):
    __tablename__ = "contracts"

    contract_number: Mapped[str] = mapped_column(String(7), primary_key=True)
    total_paid_to_date: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    membership_number: Mapped[int]
    contract_date: Mapped[date]
    original_purchase_date: Mapped[date]
    contract_price: Mapped[Decimal] = mapped_column(Numeric(7, 2))
    original_contract_price: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    down_payment_agreed: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    down_payment_fees: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    down_payment_total_due: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    down_payment_paid: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    financed_principal: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    financed_principal_paid: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    capital_pending: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    interest_total: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    interest_paid: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    interest_outstanding: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    annual_interest_rate_percent: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    payment_plan_code: Mapped[int]
    contract_term_years: Mapped[Decimal] = mapped_column(Numeric(4, 1))
    percent_paid: Mapped[Decimal] = mapped_column(Numeric(8, 1))
    previous_contract_number: Mapped[str] = mapped_column(String(7))
    next_contract_number: Mapped[str] = mapped_column(String(7))
    installments_total: Mapped[int]
    installments_pending: Mapped[int]
    installments_overdue: Mapped[int]
    monthly_payment: Mapped[str] = mapped_column(String(10))
    capital_overdue: Mapped[Decimal] = mapped_column(Numeric(7, 2))
    interest_overdue: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    first_payment_date: Mapped[date]
    cancellation_date: Mapped[date]
    payment_status: Mapped[str] = mapped_column(String(30))
    is_active: Mapped[str] = mapped_column(String(50))

    def __repr__(self):
        return f'Contracts("{self.contract_number}", {self.contract_price}, "{self.contract_date}")'


class Members(Base):
    __tablename__ = "members"

    membership_number: Mapped[str] = mapped_column(String(50), unique=True)
    phone: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime_utcnow)
    contract_price_synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    contract_number: Mapped[str] = mapped_column(String, primary_key=True)
    available_points: Mapped[int]
    paid_points: Mapped[int]
    birth_date: Mapped[date]
    email: Mapped[str] = mapped_column(String(60))
    home_phone: Mapped[str] = mapped_column(String(20))
    office_phone: Mapped[str] = mapped_column(String(20))
    dpi: Mapped[str] = mapped_column(String(13))
    passport: Mapped[str] = mapped_column(String(40))
    nit: Mapped[str] = mapped_column(String(20))
    address: Mapped[str] = mapped_column(String(90))
    postal_code: Mapped[str] = mapped_column(String(8))
    country: Mapped[str] = mapped_column(String(40))
    department: Mapped[str] = mapped_column(String(80))
    city: Mapped[str] = mapped_column(String(60))
    profesion: Mapped[str] = mapped_column(String(60))
    income: Mapped[str] = mapped_column(String(30))
    nationality: Mapped[str] = mapped_column(String(40))
    visa: Mapped[bool]
    age: Mapped[str] = mapped_column(String(3))

    def __repr__(self):
        return f'Members("{self.contract_number}", "{self.membership_number}")'

class Participant(Base):
    __tablename__ = "participants"

    id: Mapped[int] = mapped_column(primary_key=True)
    contract_number: Mapped[str] = mapped_column(
        String(10), ForeignKey("members.contract_number"), index=True
    )
    role: Mapped[str] = mapped_column(String(20))
    full_name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(120))
    mobile_phone: Mapped[str] = mapped_column(String(20))
    home_phone: Mapped[str] = mapped_column(String(20))
    office_phone: Mapped[str] = mapped_column(String(20))
    birth_date: Mapped[date]
    dpi: Mapped[str] = mapped_column(String(13))
    passport: Mapped[str] = mapped_column(String(20))
    nit: Mapped[str] = mapped_column(String(13))
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    def __repr__(self):
        return f'Participant("{self.contract_number}", "{self.full_name}", "{self.mobile_phone}")'









# call actualizarCuenta("110001");
# SELECT
# 	*
# FROM
# 	pasante
# WHERE
# 	junto = "110001";
# puntos_disponiblesSELECT DISTINCT * FROM pasante;


############################ TEMPORARY MODELS ## opus can only add below here for needed models for temp scripts

#mysql source for room_combinations, only needed by app/temp/backfill_room_combinations.py
class Combinaciones(Base):
    __tablename__ = "combinaciones"
    id: Mapped[int] = mapped_column(primary_key=True)
    hotel: Mapped[int]
    adults: Mapped[int] = mapped_column("adultos")
    kids: Mapped[int] = mapped_column("ninos")
    total: Mapped[int]
    priority: Mapped[int] = mapped_column("prioridad")
    active: Mapped[int] = mapped_column("activo")


class DetalleCombinaciones(Base):
    __tablename__ = "detalle_combinaciones"
    id: Mapped[int] = mapped_column(primary_key=True)
    combination_id: Mapped[int] = mapped_column("combinacion_id")
    unit_id: Mapped[int] = mapped_column("tipo_unid_id")
    quantity: Mapped[int] = mapped_column("cantidad")


class TipoUnid(Base):
    __tablename__ = "tipo_unid"
    id: Mapped[int] = mapped_column(primary_key=True)
    room_code: Mapped[str] = mapped_column("unidad", String(10))
    hotel: Mapped[int]
