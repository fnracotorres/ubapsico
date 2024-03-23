import os
import telebot


import ping3
import re
from datetime import datetime
import json

from typing import Optional
from sqlalchemy import ForeignKey
from sqlalchemy import String
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import relationship
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
import telebot
from dataclasses import dataclass
from typing import Dict, Optional
import socket
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy import Column, Integer, String, ForeignKey, Table
from sqlalchemy.orm import relationship
import subprocess
from sqlalchemy import DateTime, Float
from sqlalchemy import desc
import asyncio
import websockets
import os
from dotenv import load_dotenv
import sys


def is_valid_port(port):
    try:
        port = int(port)
        return 0 < port < 65536
    except ValueError:
        return False


if not len(sys.argv) >= 3:
    print(
        """Por favor, proporciona al menos dos argumentos.

Uso:     ./main <Puerto>
Ejemplo: ./main 8765"""
    )
    sys.exit(1)

port = sys.argv[1]
bot_token = sys.argv[2]
my_list_str = sys.argv[3]

print("Puerto:", port)

if not is_valid_port(port):
    print("<Puerto> invalidado.")
    sys.exit(1)

load_dotenv()


# BOT_TOKEN = os.getenv(bot_token)

from telebot.async_telebot import AsyncTeleBot

bot = AsyncTeleBot(bot_token)


class Base(DeclarativeBase):
    pass


user_desk_association = Table(
    "user_desk_association",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id")),
    Column("desk_id", Integer, ForeignKey("desks.id")),
)

user_site_association = Table(
    "user_site_association",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id")),
    Column("site_id", Integer, ForeignKey("sites.id")),
)

desk_site_association = Table(
    "desk_site_association",
    Base.metadata,
    Column("desk_id", Integer, ForeignKey("desks.id")),
    Column("site_id", Integer, ForeignKey("sites.id")),
)


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    last_site_name_said = Column(String)
    last_desk_name_said = Column(String)
    desks = relationship(
        "Desk", secondary=user_desk_association, back_populates="users"
    )
    sites = relationship(
        "Site", secondary=user_site_association, back_populates="users"
    )


class Desk(Base):
    __tablename__ = "desks"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    users = relationship(
        "User", secondary=user_desk_association, back_populates="desks"
    )
    sites = relationship(
        "Site", secondary=desk_site_association, back_populates="desks"
    )
    speed_measurements = relationship("SpeedMeasurement", back_populates="desk")


class Site(Base):
    __tablename__ = "sites"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    users = relationship(
        "User", secondary=user_site_association, back_populates="sites"
    )
    desks = relationship(
        "Desk", secondary=desk_site_association, back_populates="sites"
    )


class SpeedMeasurement(Base):
    __tablename__ = "speed_measurements"
    id = Column(Integer, primary_key=True)
    send_time = Column(DateTime)
    receive_time = Column(DateTime)
    travel_time = Column(Float)
    transmission_speed = Column(Float)
    route = Column(String)
    desk_id = Column(Integer, ForeignKey("desks.id"))
    desk = relationship("Desk", back_populates="speed_measurements")


engine = create_engine("sqlite:///bot.sqlite")

Base.metadata.create_all(engine, checkfirst=True)

from enum import Enum


class InputType(Enum):
    IP = 1
    DNS = 2
    UNREACHABLE = 3
    INVALID = 4


@dataclass
class UserState:
    state: Optional[str] = None


def check_ip_dns(input_str):
    try:
        # Try to parse the input as an IP address
        socket.inet_aton(input_str)
        return InputType.IP
    except socket.error:
        try:
            # Try to resolve the input as a DNS
            socket.gethostbyname(input_str)
            return InputType.DNS
        except socket.gaierror:
            # Input is neither a valid IP nor a valid DNS
            return InputType.INVALID


def ping_desk(desk_name, timeout=2, count=4):
    """
    Ping the specified desk and return ping result details.
    """
    try:
        # Perform the ping operation
        results = ping3.ping(desk_name, timeout=timeout, count=count)

        if results is None:
            # Ping timed out
            return {
                "desk_name": desk_name,
                "status": "unreachable",
                "error": "Ping timed out",
                "rtt_ms": None,
                "packet_loss": None,
            }
        else:
            # Ping successful
            avg_rtt = sum(results) / len(results)
            packet_loss = results.count(None) / len(results) * 100

            return {
                "desk_name": desk_name,
                "status": "reachable",
                "error": None,
                "rtt_ms": avg_rtt,
                "packet_loss": packet_loss,
            }
    except Exception as e:
        # Error occurred during ping operation
        return {
            "desk_name": desk_name,
            "status": "error",
            "error": str(e),
            "rtt_ms": None,
            "packet_loss": None,
        }


from functools import wraps

with Session(engine) as session:

    LIST_OF_ADMIN_USERNAMES = my_list_str.split(",")

    CLIENTS = set()

    def protected(func):
        @wraps(func)
        async def wrapped(message, *args, **kwargs):
            username = message.from_user.username

            if username not in LIST_OF_ADMIN_USERNAMES:
                print(f"Unauthorized access denied for {username}.")
                return

            user = session.query(User).filter(User.name == username).first()

            if not user:
                user = User(name=username)
                session.add(user)
                session.commit()
                print(f"User account created for {username}.")

            return await func(message, *args, **kwargs)

        return wrapped

    user_states: Dict[int, UserState] = {}

    @bot.message_handler(commands=["help"])
    @protected
    async def show_help(message: telebot.types.Message):
        await bot.send_message(
            message.chat.id,
            f"""Puedo ayudarte con la gestión de la Facultad. Aquí tienes los comandos disponibles:

Puedes controlarme enviando estos comandos:

<b>Sitios</b>
/newsite - añadir un nuevo sitio
/deletesite - eliminar un sitio existente

<b>Desks</b>
/newdesk - añadir un nuevo desk
/deletedesk - eliminar un desk existente
/setsite - asignar un sitio a un desk

<b>Comandos</b>
/allstatus - obtener estado de todos los desks
/status - obtener estado de desks añadidos
/sites - obtener status de sitios
/load - obtener velocidad de carga (últimas 5 por desk)""",
            parse_mode="HTML",
        )

    @bot.message_handler(commands=["newsite"])
    @protected
    async def newsite(message: telebot.types.Message):
        user_states[message.chat.id] = UserState("waiting_for_site_name_for_newsite")
        await bot.send_message(
            message.chat.id,
            "Está bien, un nuevo sitio. ¿Cuál es su dirección IP o DNS?",
        )

    @bot.message_handler(commands=["deletesite"])
    @protected
    async def deletesite(message: telebot.types.Message):
        user_states[message.chat.id] = UserState("waiting_for_site_name_for_deletesite")

        username = message.from_user.username
        user = session.query(User).filter(User.name == username).first()
        sites = user.sites

        if sites:
            message_text = "Oh, eliminar un Sitio, está bien. ¿Cuál?\n"
            for idx, site in enumerate(sites):
                message_text += f"({idx}) {site.name}\n"
            await bot.send_message(message.chat.id, message_text)
        else:
            await bot.send_message(
                message.chat.id,
                f"Actualmente, no hay ningún Sitio asignado a ninguna desk asignado a su Username {username}. Añada con /setsite.",
            )

    @bot.message_handler(commands=["newdesk"])
    @protected
    async def newdesk(message: telebot.types.Message):
        user_states[message.chat.id] = UserState("waiting_for_site_name_for_newdesk")
        await bot.send_message(
            message.chat.id,
            "Está bien, un nuevo desk. Nombre:",
        )

    @bot.message_handler(commands=["deletedesk"])
    @protected
    async def deletedesk(message: telebot.types.Message):
        user_states[message.chat.id] = UserState("waiting_for_desk_name_for_deletedesk")

        username = message.from_user.username
        user = session.query(User).filter(User.name == username).first()
        desks = user.desks

        if desks:
            message_text = "Oh, eliminar un desk, está bien. ¿Cuál?\n"
            for idx, desk in enumerate(desks):
                message_text += f"({idx}) {desk.name}\n"
            await bot.send_message(message.chat.id, message_text)
        else:
            await bot.send_message(
                message.chat.id,
                f"Actualmente, no hay ningún Desk asignado a su Username {username}. Añada con /newdesk.",
            )

    @bot.message_handler(commands=["setsite"])
    @protected
    async def setsite(message: telebot.types.Message):
        username = message.from_user.username
        user = session.query(User).filter(User.name == username).first()

        sites = user.sites

        user_states[message.chat.id] = UserState("waiting_for_site_name_for_setsite")

        if sites:
            message_text = "Seleciona el nombre del sitio para seguir. ¿Cuál?\n"
            for idx, site in enumerate(sites):
                message_text += f"({idx}) {site.name}\n"
            await bot.send_message(message.chat.id, message_text)
        else:
            await bot.send_message(
                message.chat.id,
                f"Actualmente, no hay ningún Sitio asignado a ninguna Desk asignado a su Username {username}. Añada con /setsite.",
            )

    @bot.message_handler(commands=["sites", "site", "checksites", "checksite"])
    @protected
    async def sites(message: telebot.types.Message):
        username = message.from_user.username
        user = session.query(User).filter(User.name == username).first()

        desks = user.desks

        if not desks:
            await bot.send_message(
                message.chat.id, "No hay desks añadidos. Añada con /newdesk."
            )
            return

        q = False

        for desk in desks:
            sites = desk.sites

            if sites:
                for site in sites:
                    if site:
                        q = True
                        break

        if not q:
            await bot.send_message(
                message.chat.id,
                "No hay ningún Site en ningún Desk. Añada con /setsite.",
            )
            return

        for desk in desks:
            sites = desk.sites

            if not sites:
                return

            site_names = [site.name for site in sites]

            reqq = {
                "kind": "sites",
                "site_names": site_names,
                "message_chat_id": message.chat.id,
            }

            json_data = json.dumps(reqq)

            broadcast(json_data)

    @bot.message_handler(
        commands=["load", "loads", "checkload", "checkloads", "info", "speed"]
    )
    @protected
    async def load(message: telebot.types.Message):
        username = message.from_user.username
        user = session.query(User).filter(User.name == username).first()

        desks = user.desks

        if not desks:
            await bot.send_message(
                message.chat.id, "No hay desks añadidos. Añada con /newdesk."
            )
            return

        text_message = ""

        q = False

        for desk in desks:
            speed_measurements = desk.speed_measurements

            if speed_measurements:
                for speed_measurement in speed_measurements:
                    if speed_measurement:
                        q = True
                        break

        if not q:
            await bot.send_message(
                message.chat.id, "No hay ninguna Métrica de Velocidad en ningún Desk."
            )
            return

        for desk in desks:
            measurements = (
                session.query(SpeedMeasurement)
                .where(SpeedMeasurement.desk_id == desk.id)
                .order_by(desc(SpeedMeasurement.id))
                .all()
            )

            if not measurements:
                await bot.send_message(
                    message.chat.id,
                    f"No hay Métrica de Velocidad de {desk.name}.",
                )
                return

            total_travel_time = 0
            total_transmission_speed = 0

            for measurement in measurements:
                total_travel_time += measurement.travel_time
                total_transmission_speed += measurement.transmission_speed

            average_travel_time = total_travel_time / len(measurements)
            average_transmission_speed = total_transmission_speed / len(measurements)

            text_message += f"Para {desk.name}:\n"
            text_message += f"    Promedio del tiempo de viaje: {average_travel_time}\n"
            text_message += f"    Promedio de la velocidad de transmisión: {average_transmission_speed}\n\n"

            text_message += "    Ultimas 5 medidas de velocidad:\n"
            for measurement in measurements[:5]:
                # Clasificación para travel_time
                if measurement.travel_time < average_travel_time:
                    travel_time_status = "DEBAJO DEL PROMEDIO"
                else:
                    travel_time_status = "ARRIBA DEL PROMEDIO"

                # Clasificación para transmission_speed
                if measurement.transmission_speed < average_transmission_speed:
                    transmission_speed_status = "DEBAJO DEL PROMEDIO"
                else:
                    transmission_speed_status = "ARRIBA DEL PROMEDIO"

                # Imprime el estado de cada instancia
                text_message += f"    {measurement.id}\n"
                text_message += f"        Travel Time: {measurement.travel_time}\n"
                text_message += f"            Status: {travel_time_status}\n"
                text_message += (
                    f"        Transmission Speed: {measurement.transmission_speed}\n"
                )
                text_message += f"            Status: {transmission_speed_status}\n\n"

                text_message += f"Trace:\n{measurement.route}\n"

            await bot.send_message(message.chat.id, text_message)

    @bot.message_handler(commands=["whosthere", "allstatus", "allreport"])
    @protected
    async def whosthere(message: telebot.types.Message):
        reqq = {
            "kind": "whosthere",
            "message_chat_id": message.chat.id,
        }

        json_data = json.dumps(reqq)

        broadcast(json_data)

    @bot.message_handler(commands=["status", "report"])
    @protected
    async def status(message: telebot.types.Message):
        desks = session.query(Desk).all()

        if not desks:
            await bot.send_message(
                message.chat.id,
                "No tienes desks para que se reporten (si estan predidios o apagados.) Añada con /newdesk.",
            )
            return

        await bot.send_message(
            message.chat.id, "Los desks seteados en el host (/newdesk) ..."
        )

        desk_names = [desk.name for desk in desks]

        reqq = {
            "kind": "status",
            "desk_names": desk_names,
            "message_chat_id": message.chat.id,
        }

        json_data = json.dumps(reqq)

        broadcast(json_data)

    @bot.message_handler(
        func=lambda message: user_states.get(message.chat.id) is not None
        and user_states.get(message.chat.id).state
        == "waiting_for_site_name_for_setsite"
    )
    @protected
    async def capture_site_name_for_setsite(message: telebot.types.Message):
        site_name = message.text

        username = message.from_user.username
        user = session.query(User).filter(User.name == username).first()
        sites = user.sites

        if sites:
            exists = False

            if site_name.isdigit():
                for idx, site in enumerate(sites):
                    if idx == int(site_name):
                        site_name = site.name
                        exists = True
                        break
                else:
                    await bot.send_message(
                        message.chat.id,
                        f"El índice {idx} no coincide con ningún nombre de sitio.",
                    )
            else:
                for site in sites:
                    if site.name == site_name:
                        exists = True
                        break
                else:
                    await bot.send_message(
                        message.chat.id,
                        f"El nombre del sitio {site_name} no coincide con ningún sitio.",
                    )

            if exists:
                await bot.send_message(
                    message.chat.id,
                    f"El sitio {site_name} ha sido selecionado correctamente.",
                )

                user.last_site_name_said = site_name

                session.commit()

                desks = user.desks

                if desks:
                    user_states[message.chat.id] = UserState(
                        "waiting_for_desk_name_for_setsite"
                    )

                    message_text = "Selecione una desk para terminar. ¿Cuál?\n"
                    for idx, desk in enumerate(desks):
                        message_text += f"({idx}) {desk.name}\n"
                    await bot.send_message(message.chat.id, message_text)
                else:
                    user_states[message.chat.id] = UserState()

                    await bot.send_message(
                        message.chat.id,
                        f"Actualmente, no hay ningún Desk asignado a su Username {username}. Añada con /newdesk.",
                    )
        else:
            user_states[message.chat.id] = UserState()

            await bot.send_message(
                message.chat.id,
                f"Actualmente, no hay ningún Sitio asignado a ningún Desk con su Username {username}. Añada con /setsite.",
            )

    @bot.message_handler(
        func=lambda message: user_states.get(message.chat.id) is not None
        and user_states.get(message.chat.id).state
        == "waiting_for_desk_name_for_setsite"
    )
    @protected
    async def capture_desk_name_for_setsite(message: telebot.types.Message):
        desk_name = message.text

        username = message.from_user.username
        user = session.query(User).filter(User.name == username).first()
        desks = user.desks

        if desks:
            exists = False

            if desk_name.isdigit():
                for idx, desk in enumerate(desks):
                    if idx == int(desk_name):
                        desk_name = desk.name
                        exists = True
                        break
                else:
                    await bot.send_message(
                        message.chat.id,
                        f"El índice {idx} no coincide con ningún nombre de desk.",
                    )
            else:
                for desk in desks:
                    if desk.name == desk_name:
                        exists = True
                        break
                else:
                    await bot.send_message(
                        message.chat.id,
                        f"El nombre del sitio {desk_name} no coincide con ningún desk.",
                    )

            if exists:
                await bot.send_message(
                    message.chat.id,
                    f"El desk {desk_name} ha sido selecionado correctamente.",
                )

                site_name = user.last_site_name_said

                site = session.query(Site).filter(Site.name == site_name).first()

                desk = session.query(Desk).filter(Desk.name == desk_name).first()
                desk.sites.append(site)

                session.commit()
        else:
            user_states[message.chat.id] = UserState()

            await bot.send_message(
                message.chat.id,
                f"Actualmente, no hay ningún Desk asignado a su Username {username}. Añada con /newdesk.",
            )

    @bot.message_handler(
        func=lambda message: user_states.get(message.chat.id) is not None
        and user_states.get(message.chat.id).state
        == "waiting_for_site_name_for_newsite"
    )
    @protected
    async def capture_site_name_for_newsite(message: telebot.types.Message):
        site_name = message.text

        result = check_ip_dns(site_name)

        await bot.send_message(message.chat.id, f"El sitio es: {site_name}")

        if result == InputType.INVALID:
            await bot.send_message(
                message.chat.id,
                f"{site_name} no es una dirección IP válida o un nombre de dominio. Inténtalo de nuevo.",
            )
        else:
            site = Site(name=site_name)
            session.add(site)
            username = message.from_user.username

            user = session.query(User).filter(User.name == username).first()
            user.sites.append(site)

            session.commit()

            user_states[message.chat.id] = UserState()

            if result == InputType.IP:
                await bot.send_message(
                    message.chat.id,
                    f"¡Listo! Has añadido la dirección IP. Algunos sitios bloquean el acceso mediante IP, como Stack Overflow, por ejemplo.",
                )
            elif result == InputType.DNS:
                await bot.send_message(
                    message.chat.id, f"¡Listo! Has añadido la dirección DNS"
                )

    @bot.message_handler(
        func=lambda message: user_states.get(message.chat.id) is not None
        and user_states.get(message.chat.id).state
        == "waiting_for_desk_names_for_newsite"
    )
    @protected
    async def capture_desk_names_for_newsite(message: telebot.types.Message):
        desk_name = message.text
        result = ping_desk(desk_name)
        if result == "reachable":
            desk = Desk(name=desk_name)
            session.add(desk)
            session.commit()
            user_states[message.chat.id] = UserState()
            await bot.send_message(
                message.chat.id,
                f"""El desk {result.desk_name} está accesible.
Tiempo promedio de ida y vuelta: {result.rtt} ms.
Pérdida de paquetes: {result.packet_loss}%.
Se ha añadido correctamente.""",
            )
        else:
            if result == "unreachable":
                user_states[message.chat.id] = UserState(
                    "waiting_for_confirmation_for_desk_names_for_newsite"
                )
                await bot.send_message(
                    message.chat.id,
                    f"""El desk {result.desk_name} no se encuentra disponible en este momento.
Por favor, verifica tu conexión a internet y asegúrate de que
el desk esté correctamente configurado.
¿Estás seguro de añadir {result.desk_name} de todos modos? s/N""",
                )
            elif result == "error":
                await bot.send_message(
                    message.chat.id,
                    f"""Se produjo un error al intentar hacer ping al desk {result.desk_name}.
Detalles del error: {result.error_message}.
Por favor, inténtalo de nuevo más tarde.
¿Estás seguro de añadir {result.desk_name} de todos modos? s/N""",
                )

    @bot.message_handler(
        func=lambda message: user_states.get(message.chat.id) is not None
        and user_states.get(message.chat.id).state
        == "waiting_for_confirmation_for_desk_names_for_newsite"
    )
    @protected
    async def capture_confirmation_for_desk_names_for_newsite(
        message: telebot.types.Message,
    ):
        user_states[message.chat.id] = UserState()
        if re.match(r"[sSyY]", message.text):
            await bot.send_message(
                message.chat.id,
                "¡Listo! Nombre de desk añadido con éxito. Ahora puedes utilizar este nombre para operar.",
            )
        else:
            await bot.send_message(
                message.chat.id,
                """Entendido, el nombre de desk no ha sido añadido.
Si decides cambiar de opinión, estoy aquí para ayudarte en cualquier momento.""",
            )

    @bot.message_handler(
        func=lambda message: user_states.get(message.chat.id) is not None
        and user_states.get(message.chat.id).state
        == "waiting_for_site_name_for_deletesite"
    )
    @protected
    async def capture_site_name_for_deletesite(message: telebot.types.Message):
        site_name = message.text

        username = message.from_user.username
        user = session.query(User).filter(User.name == username).first()
        sites = user.sites

        if sites:
            exists = False

            if site_name.isdigit():
                for idx, site in enumerate(sites):
                    if idx == int(site_name):
                        site_name = site.name
                        exists = True
                        break
                else:
                    await bot.send_message(
                        message.chat.id,
                        f"El índice {idx} no coincide con ningún nombre de sitio.",
                    )
            else:
                for site in sites:
                    if site.name == site_name:
                        exists = True
                        break
                else:
                    await bot.send_message(
                        message.chat.id,
                        f"El nombre del sitio {site_name} no coincide con ningún sitio.",
                    )

            if exists:
                site = session.query(Site).filter(Site.name == site_name).first()
                session.delete(site)

                session.commit()

                user_states[message.chat.id] = UserState()

                await bot.send_message(
                    message.chat.id, f"El sitio {site_name} ha sido eliminado."
                )
        else:
            user_states[message.chat.id] = UserState()

            await bot.send_message(
                message.chat.id,
                f"Actualmente, no hay ningún Sitio asignado a ningún Desk con su Username {username}. Añada con /setsite.",
            )

    # def is_reachable_desk(desk):
    #     try:
    #         result = subprocess.run(
    #             ["ping", "-c", "1", "-W", "5", desk],  # -W option sets timeout to 5 seconds
    #             stdout=subprocess.PIPE,
    #             stderr=subprocess.PIPE,
    #             text=True,
    #             timeout=10,  # Set a longer overall timeout for the subprocess
    #         )
    #         if result.returncode == 0:
    #             return True
    #         else:
    #             return False
    #     except Exception as e:
    #         print("An error occurred:", e)
    #         return False

    @bot.message_handler(
        func=lambda message: user_states.get(message.chat.id) is not None
        and user_states.get(message.chat.id).state
        == "waiting_for_site_name_for_newdesk"
    )
    @protected
    async def capture_desk_name_for_newdesk(message: telebot.types.Message):
        desk_name = message.text

        await bot.send_message(message.chat.id, f"El nombre del desk es: {desk_name}.")

        # if not is_reachable_desk(desk_name):
        #     await bot.send_message(
        #         message.chat.id,
        #         f"No puedo alcanzar a {desk_name} en la red. Itente de nuevo, con otro nombre, o verifique el desk.",
        #     )
        # else:
        desk = Desk(name=desk_name)
        session.add(desk)
        username = message.from_user.username

        user = session.query(User).filter(User.name == username).first()
        user.desks.append(desk)

        session.commit()

        user_states[message.chat.id] = UserState()

        await bot.send_message(
            message.chat.id,
            f"¡Listo! El nombre del desk {desk_name} se ha añadido correctamente",
        )

    @bot.message_handler(
        func=lambda message: user_states.get(message.chat.id) is not None
        and user_states.get(message.chat.id).state
        == "waiting_for_desk_name_for_deletedesk"
    )
    @protected
    async def capture_desk_name_for_deletedesk(message: telebot.types.Message):
        desk_name = message.text

        username = message.from_user.username
        user = session.query(User).filter(User.name == username).first()
        desks = user.desks

        if desks:
            exists = False

            if desk_name.isdigit():
                for idx, desk in enumerate(desks):
                    if idx == int(desk_name):
                        desk_name = desk.name
                        exists = True
                        break
                else:
                    await bot.send_message(
                        message.chat.id,
                        f"El índice {idx} no coincide con ningún nombre de sitio.",
                    )
            else:
                for desk in desks:
                    if desk.name == desk_name:
                        exists = True
                        break
                else:
                    await bot.send_message(
                        message.chat.id,
                        f"El nombre del sitio {desk_name} no coincide con ningún sitio.",
                    )
            if exists:

                desk = session.query(Desk).filter(Desk.name == desk_name).first()
                session.delete(desk)

                session.commit()

                user_states[message.chat.id] = UserState()

                await bot.send_message(
                    message.chat.id, f"El sitio {desk_name} ha sido eliminado."
                )
        else:
            user_states[message.chat.id] = UserState()

            await bot.send_message(
                message.chat.id,
                f"Actualmente, no hay ningún Desk asignado a su Username {username}. Añada con /newdesk.",
            )

    async def send(websocket, message):
        try:
            await websocket.send(message)
        except websockets.ConnectionClosed:
            pass

    def broadcast(message):
        for websocket in CLIENTS:
            asyncio.create_task(send(websocket, message))

    async def handler(websocket):
        CLIENTS.add(websocket)
        try:
            async for message in websocket:
                task = json.loads(message)

                kind = task["kind"]

                if kind == "status":
                    message_chat_id = task["message_chat_id"]
                    desk_name = task["desk_name"]
                    print(message_chat_id)
                    print(desk_name)
                    await bot.send_message(
                        message_chat_id, f"EJECUTANDOSE: {desk_name}.\n"
                    )
                elif kind == "sites":
                    desk_name = task["desk_name"]

                    text_message = f"Los estados de los sitios para {desk_name} son:\n"

                    message_chat_id = task["message_chat_id"]

                    text_message += task["more_text"]

                    await bot.send_message(message_chat_id, text_message)

                elif kind == "load":
                    desk_name = task["desk_name"]

                    if not desk_name:
                        print("No desk_name was provided in load.")
                        continue

                    desk = session.query(Desk).filter(Desk.name == desk_name).first()

                    speed_measurement = task["data"]

                    speed_measurementq = SpeedMeasurement(
                        send_time=datetime.strptime(
                            speed_measurement["send_time"], "%Y-%m-%d %H:%M:%S.%f"
                        ),
                        receive_time=datetime.strptime(
                            speed_measurement["receive_time"], "%Y-%m-%d %H:%M:%S.%f"
                        ),
                        travel_time=speed_measurement["travel_time"],
                        transmission_speed=speed_measurement["transmission_speed"],
                        route=speed_measurement["route"],
                    )

                    session.add(speed_measurementq)

                    desk.speed_measurements.append(speed_measurementq)

                    print(f"Se agrego {speed_measurementq.id} en")
                    print(f"{desk.id} {desk.name}")

                    session.commit()
        except websockets.ConnectionClosedError:
            pass
        finally:
            CLIENTS.remove(websocket)

    async def start_server():
        async with websockets.serve(handler, "localhost", port, ping_interval=None):
            await asyncio.Future()

    async def start_bot():
        await bot.polling()

    async def main():
        await asyncio.gather(start_server(), start_bot())

    if __name__ == "__main__":
        asyncio.run(main())
