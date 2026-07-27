from datetime import datetime, timezone, date
from uuid import UUID, uuid4
from app.database import Base
from pydantic import BaseModel
from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship


#UPDATE NEEDED.
# 1) PRICE IS HARD CODED, UPDATE DB TO DO THAT
def datetime_utcnow():
    return datetime.now(timezone.utc)

# The JSON body the browser sends to POST /chat.
class ChatRequest(BaseModel):
    conversation_id: str | None = None
    message: str

#convention [table name is lower clase and plural form of the entity] [class name is Singular form in Camel case]
class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[UUID] = mapped_column(default=uuid4, primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(default=datetime_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime_utcnow, onupdate=datetime_utcnow
    )

    def __repr__(self):
        return f'Conversation({self.id}, "{self.timestamp}", "{self.updated_at}")'

class Message(Base):
    __tablename__ = "messages"

    id: Mapped[UUID] = mapped_column(default=uuid4, primary_key=True)
    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversations.id"), index=True
    )
    role: Mapped[str] = mapped_column(String(10))
    message: Mapped[list | str] = mapped_column(JSON)
    timestamp: Mapped[datetime] = mapped_column(default=datetime_utcnow)

    def __repr__(self):
        return f'Message({self.id}, "{self.conversation_id}", "{self.role}", "{self.message}, "{self.timestamp}"")'

class Combination(Base):
    __tablename__ = "combinaciones"
    id: Mapped[int] = mapped_column(primary_key=True) #441, this
    hotel: Mapped[int]
    priority: Mapped[int]=mapped_column("prioridad")
    active:Mapped[int]=mapped_column("activo")
    adults: Mapped[int] = mapped_column("adultos")
    children: Mapped[int] = mapped_column("ninos")
    total: Mapped[int]

    details: Mapped[list["Detail"]] = relationship(back_populates="combination")
    
    def __repr__(self):
        return f'Combination(id={self.id}, hotel={self.hotel}, adults={self.adults}, children={self.children}, priority={self.priority}, total={self.total})'

class Detail(Base):
    __tablename__ = "detalle_combinaciones"
    id: Mapped[int] = mapped_column(primary_key=True) 
    combination_id: Mapped[int] = mapped_column("combinacion_id", ForeignKey("combinaciones.id"))#440, #441, uses PK of Combinations 
    unit_id: Mapped[int] = mapped_column("tipo_unid_id", ForeignKey("tipo_unid.id"))
    quantity: Mapped[int] = mapped_column("cantidad")

    combination: Mapped["Combination"] = relationship(back_populates="details")
    unit: Mapped["Unit_type"] = relationship(back_populates="details")

    def __repr__(self):
        return f'Detail(id={self.id}, combinacion_id={self.combination_id}, tipo_unid_id={self.unit_id}, quantity={self.quantity})'



class Unit_type(Base):
    __tablename__ = "tipo_unid"
    id: Mapped[int] = mapped_column(primary_key=True) #1,3,4,5 #units pk, b1br
    room_id: Mapped[str] = mapped_column("unidad") #D2DL
    hotel_id: Mapped[int] = mapped_column("HOTEL")
    room_name: Mapped[str] = mapped_column("nombre") #nombre Bungalo de 4

    details: Mapped[list["Detail"]] = relationship(back_populates="unit")
    allotments: Mapped[list["Allotment"]] = relationship(back_populates="unit")

    def __repr__(self):
        return f'Unit({self.hotel_id}, "{self.room_id}", "{self.room_name}")'

class Allotment(Base):
    __tablename__ = "allotment"
    allotment_id: Mapped[int] = mapped_column("corr", primary_key=True)
    hotel_id: Mapped[int] = mapped_column("HOTEL") 
    room_id: Mapped[str] = mapped_column("unidad", ForeignKey("tipo_unid.unidad"))
    check_in: Mapped[date] =mapped_column("entra")
    check_out: Mapped[date] =mapped_column("sale")
    estado: Mapped[str] = mapped_column("estado")
    membership_number: Mapped[str] = mapped_column("JUNTO")
    name: Mapped[str] = mapped_column("NOMBRE")

    unit: Mapped["Unit_type"] = relationship(back_populates="allotments")

    def __repr__(self):
        return f'Allotment({self.allotment_id}, "{self.hotel_id}", "{self.room_id}",  "{self.check_in}",  "{self.check_out}",  "{self.estado}",  "{self.membership_number}",  "{self.name}")'

class ExchangeRate(Base):
    __tablename__ = "tasa"
    id:Mapped[int] = mapped_column("corr", primary_key=True)
    today:Mapped[date] = mapped_column("fecha")
    rate:Mapped[float] = mapped_column("tasa")

    def __repr__(self):
        return f'Rate({self.id}, "{self.date}", "{self.rate}")'

class Destination(Base):
    __tablename__ = "destino"
    id:Mapped[int] = mapped_column("corr", primary_key=True)
    points: Mapped[float] = mapped_column("NUMPUN")#MULTIPLY BY 4.5
    hotel_name: Mapped[str] = mapped_column("LUGARUSO")#SOLEIL LA ANTIGUA OR SOLEIL PACIFICO
    hotel_id: Mapped[int] = mapped_column("CVELUG") #1 or 2
    room_id: Mapped[str] = mapped_column("CVEUNI")
    year:Mapped[int] = mapped_column("anocta")
    day: Mapped[str] = mapped_column("FINENTRE")#FIN, ENTRE, SUP_AL

    def __repr__(self):
        return f'Destination({self.id}, "{self.points}", "{self.hotel_name}", "{self.hotel_id}", "{self.room_id}", "{self.year}", "{self.season}")'

#add visible web 


class SeasonCalendar(Base):
    id: Mapped[int] = mapped_column("corr", primary_key=True)
    __tablename__ = "tarifa_hotel2"
    season: Mapped[str] = mapped_column("temporada") #ENTRE SEMANA, FIN DE SEMANA, SUPER ALTA, BUT WILL BE FIN, ENTRE, SUP_AL
    calendar: Mapped[date] = mapped_column("fecha")


class Pasante(Base):
    __tablename__ = "pasante"
    id: Mapped[int] = mapped_column("corr", primary_key=True)
    membership_number: Mapped[str] = mapped_column("junto")
    available_points: Mapped[int] = mapped_column("puntos_disponibles")



# call actualizarCuenta("110001");
# SELECT
# 	*
# FROM
# 	pasante
# WHERE
# 	junto = "110001";
# puntos_disponiblesSELECT DISTINCT * FROM pasante;