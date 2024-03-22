from scapy.all import *
from scapy.layers.inet import ICMP, IP, UDP
from sqlalchemy import create_engine, Column, Integer, Float, String, DateTime
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import DeclarativeBase
import schedule
from sqlalchemy.orm import Session
import json
import time
from datetime import datetime
import asyncio
from websockets.sync.client import connect
import websockets
import socket
from urllib.parse import urlparse
import requests
import sys
import ipaddress


def is_valid_ip(ip):
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False


def is_valid_port(port):
    try:
        port = int(port)
        return 0 < port < 65536
    except ValueError:
        return False


if not len(sys.argv) >= 3:
    print(
        """Por favor, proporciona al menos dos argumentos.

Uso:     ./main <Dirección IP> <Puerto>
Ejemplo: ./main 127.0.0.1 8765"""
    )
    exit(1)

ip = sys.argv[1]
port = sys.argv[2]

if not is_valid_ip(ip):
    print("<Dirección IP> invalidada.")
    exit(1)

if not is_valid_port(port):
    print("<Puerto> invalidado.")
    exit(1)

print("Dirección IP:", ip)
print("Puerto:", port)

destination = ip

engine = create_engine("sqlite:///speed_measurements.db")


class Base(DeclarativeBase):
    pass


class SpeedMeasurement(Base):
    __tablename__ = "speed_measurements"
    id = Column(Integer, primary_key=True)
    send_time = Column(DateTime)
    receive_time = Column(DateTime)
    travel_time = Column(Float)
    transmission_speed = Column(Float)
    route = Column(String)


Base.metadata.create_all(engine)


def traceroute(destination, max_hops=15, timeout=2):
    port = 33434
    ttl = 1
    txt = ""
    while True:
        ip_packet = IP(dst=destination, ttl=ttl)
        udp_packet = UDP(dport=port)

        packet = ip_packet / udp_packet

        reply = sr1(packet, timeout=timeout, verbose=0)

        if reply is None:
            txt += f"{ttl}\t*\n"
        elif reply.type == 3:
            txt += f"{ttl}\t{reply.src}\n"
            break
        else:
            txt += f"{ttl}\t{reply.src}\n"

        ttl += 1

        if ttl > max_hops:
            break
    return txt


# Define la función para medir la velocidad de transmisión y realizar el traceroute
def measure_speed_and_trace():
    def measure_speed():
        packet = IP(dst=destination) / ICMP()
        send_time = datetime.now()
        sr1(packet, timeout=2, verbose=False)
        receive_time = datetime.now()
        travel_time = (receive_time - send_time).total_seconds()
        transmission_speed = (len(packet) * 8) / (travel_time * 10**6)

        # print(f"Destino: {destination}")
        print("Tiempo de emisión:", send_time)
        print("Tiempo de llegada:", receive_time)
        print("Tiempo total de viaje:", travel_time)
        print("Velocidad de transmisión:", transmission_speed, "Mbps")

        return send_time, receive_time, travel_time, transmission_speed

    send_time, receive_time, travel_time, transmission_speed = measure_speed()

    route = traceroute(destination=destination, max_hops=30, timeout=2)

    print("Trace:")
    print(route)

    new_measurement = SpeedMeasurement(
        send_time=send_time,
        receive_time=receive_time,
        travel_time=travel_time,
        transmission_speed=transmission_speed,
        route=route,
    )

    return new_measurement


def check_website(url):
    try:
        parsed_url = urlparse(url)
        if not parsed_url.scheme:
            url = "http://" + url
        response = requests.get(url)

        if response.status_code == 200:
            return True
        else:
            return False
    except requests.ConnectionError:
        print(f"Could not connect to {url}. It may be down or the URL is invalid.")
        return False


with Session(engine) as session:

    def hello():
        with connect(f"ws://{ip}:{port}") as websocket:

            def doit():
                print(websocket)
                speed_measurement = measure_speed_and_trace()
                session.add(speed_measurement)

                session.commit()

                serialized_measurement = {
                    "id": speed_measurement.id,
                    "send_time": str(speed_measurement.send_time),
                    "receive_time": str(speed_measurement.receive_time),
                    "travel_time": speed_measurement.travel_time,
                    "transmission_speed": speed_measurement.transmission_speed,
                    "route": speed_measurement.route,
                }

                reqq = {
                    "kind": "load",
                    "desk_name": socket.gethostname(),
                    "data": serialized_measurement,
                }
                json_data = json.dumps(reqq)

                websocket.send(json_data)

            for _ in range(1):
                doit()

            schedule.every().day.at("09:00").do(doit)
            schedule.every().day.at("19:00").do(doit)

            while True:
                schedule.run_pending()
                time.sleep(1)
                try:
                    message = websocket.recv()
                    task = json.loads(message)
                    kind = task["kind"]
                    print(kind)
                    if kind == "whosthere":
                        desk_name = socket.gethostname()
                        reqq = {
                            "kind": "status",
                            "desk_name": desk_name,
                            "message_chat_id": task["message_chat_id"],
                        }
                        json_data = json.dumps(reqq)
                        websocket.send(json_data)
                    if kind == "status":
                        desk_name = socket.gethostname()
                        print(desk_name)
                        if desk_name in task["desk_names"]:
                            reqq = {
                                "kind": "status",
                                "desk_name": desk_name,
                                "message_chat_id": task["message_chat_id"],
                            }
                            json_data = json.dumps(reqq)
                            websocket.send(json_data)
                    elif kind == "sites":
                        desk_name = socket.gethostname()

                        site_names = task["site_names"]

                        more_text = ""

                        for site_name in site_names:
                            is_available_site = check_website(site_name)

                            if is_available_site:
                                more_text += f"    - {site_name} FUNCIONANDO\n"
                            else:
                                more_text += f"    - {site_name} ERROR\n"

                        reqq = {
                            "kind": "sites",
                            "desk_name": desk_name,
                            "more_text": more_text,
                            "message_chat_id": task["message_chat_id"],
                        }

                        json_data = json.dumps(reqq)

                        websocket.send(json_data)
                except websockets.ConnectionClosed:
                    print(f"Terminated")
                    break

    if __name__ == "__main__":
        hello()
