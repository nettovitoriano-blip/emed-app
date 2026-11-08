"""
EMED Eletromedicina - Gateway TCP Nativo de Telemetria GPS (Protocolo GT06 / J16 4G)
Recebe dados brutos via TCP do rastreador J16 / G900L, realiza o handshake,
decodifica satélites, latitude, longitude, velocidade, ignição e odômetro,
e sincroniza em tempo real com o banco de dados oficial (emed.db).
"""
import asyncio
import datetime
import math
import os
import sqlite3
import struct
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
from typing import Optional, Tuple

from emed_frota_gps import registrar_telemetria_ou_viagem_gps

# Tabela CRC16 X.25 padrão oficial do protocolo Concox / WanWay / GT06
CRCTAB16 = [
    0x0000, 0x1189, 0x2312, 0x329B, 0x4624, 0x57AD, 0x6536, 0x74BF,
    0x8C48, 0x9DC1, 0xAF5A, 0xBED3, 0xCA6C, 0xDBE5, 0xE97E, 0xF8F7,
    0x1081, 0x0108, 0x3393, 0x221A, 0x56A5, 0x472C, 0x75B7, 0x643E,
    0x9CC9, 0x8D40, 0xBFDB, 0xAE52, 0xDAED, 0xCB64, 0xF9FF, 0xE876,
    0x2102, 0x308B, 0x0210, 0x1399, 0x6726, 0x76AF, 0x4434, 0x55BD,
    0xAD4A, 0xBCC3, 0x8E58, 0x9FD1, 0xEB6E, 0xFAE7, 0xC87C, 0xD9F5,
    0x3183, 0x200A, 0x1291, 0x0318, 0x77A7, 0x662E, 0x54B5, 0x453C,
    0xBDCB, 0xAC42, 0x9ED9, 0x8F50, 0xFBEF, 0xEA66, 0xD8FD, 0xC974,
    0x4204, 0x538D, 0x6116, 0x709F, 0x0420, 0x15A9, 0x2732, 0x36BB,
    0xCE4C, 0xDFC5, 0xED5E, 0xFCD7, 0x8868, 0x99E1, 0xAB7A, 0xBAF3,
    0x5285, 0x430C, 0x7197, 0x601E, 0x14A1, 0x0528, 0x37B3, 0x263A,
    0xDECD, 0xCF44, 0xFDDF, 0xEC56, 0x98E9, 0x8960, 0xBBFB, 0xAA72,
    0x6306, 0x728F, 0x4014, 0x519D, 0x2522, 0x34AB, 0x0630, 0x17B9,
    0xEF4E, 0xFEC7, 0xCC5C, 0xDDD5, 0xA96A, 0xB8E3, 0x8A78, 0x9BF1,
    0x7387, 0x620E, 0x5095, 0x411C, 0x35A3, 0x242A, 0x16B1, 0x0738,
    0xFFCF, 0xEE46, 0xDCDD, 0xCD54, 0xB9EB, 0xA862, 0x9AF9, 0x8B70,
    0x8408, 0x9581, 0xA71A, 0xB693, 0xC22C, 0xD3A5, 0xE13E, 0xF0B7,
    0x0840, 0x19C9, 0x2B52, 0x3ADB, 0x4E64, 0x5FED, 0x6D76, 0x7CFF,
    0x9489, 0x8500, 0xB79B, 0xA612, 0xD2AD, 0xC324, 0xF1BF, 0xE036,
    0x18C1, 0x0948, 0x3BD3, 0x2A5A, 0x5EE5, 0x4F6C, 0x7DF7, 0x6C7E,
    0xA50A, 0xB483, 0x8618, 0x9791, 0xE32E, 0xF2A7, 0xC03C, 0xD1B5,
    0x2942, 0x38CB, 0x0A50, 0x1BD9, 0x6F66, 0x7EEF, 0x4C74, 0x5DFD,
    0xB58B, 0xA402, 0x9699, 0x8710, 0xF3AF, 0xE226, 0xD0BD, 0xC134,
    0x39C3, 0x284A, 0x1AD1, 0x0B58, 0x7FE7, 0x6E6E, 0x5CF5, 0x4D7C,
    0xC60C, 0xD785, 0xE51E, 0xF497, 0x8028, 0x91A1, 0xA33A, 0xB2B3,
    0x4A44, 0x5BCD, 0x6956, 0x78DF, 0x0C60, 0x1DE9, 0x2F72, 0x3EFB,
    0xD68D, 0xC704, 0xF59F, 0xE416, 0x90A9, 0x8120, 0xB3BB, 0xA232,
    0x5AC5, 0x4B4C, 0x79D7, 0x685E, 0x1CE1, 0x0D68, 0x3FF3, 0x2E7A,
    0xE70E, 0xF687, 0xC41C, 0xD595, 0xA12A, 0xB0A3, 0x8238, 0x93B1,
    0x6B46, 0x7ACF, 0x4854, 0x59DD, 0x2D62, 0x3CEB, 0x0E70, 0x1FF9,
    0xF78F, 0xE606, 0xD49D, 0xC514, 0xB1AB, 0xA022, 0x92B9, 0x8330,
    0x7BC7, 0x6A4E, 0x58D5, 0x495C, 0x3DE3, 0x2C6A, 0x1EF1, 0x0F78
]

def crc16_x25(data: bytes) -> int:
    crc = 0xFFFF
    for b in data:
        crc = (crc >> 8) ^ CRCTAB16[(crc ^ b) & 0xFF]
    return (~crc) & 0xFFFF

def gerar_pacote_ack(protocol_byte: int, serial_bytes: bytes) -> bytes:
    """Monta o pacote de resposta oficial: 78 78 05 [PROTOCOLO] [SERIAL] [CRC16] 0D 0A"""
    body = bytes([0x05, protocol_byte]) + serial_bytes
    crc = crc16_x25(body)
    return bytes([0x78, 0x78]) + body + bytes([(crc >> 8) & 0xFF, crc & 0xFF, 0x0D, 0x0A])

class GT06ClientSession:
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, db_name: str):
        self.reader = reader
        self.writer = writer
        self.db_name = db_name
        self.addr = writer.get_extra_info("peername")
        self.imei: Optional[str] = None
        self.placa = "EMD-2026"

    async def run(self):
        print(f"🛰️ [EMED-GPS] Nova conexão do rastreador J16 recebida de: {self.addr}")
        buffer = bytearray()
        try:
            while not self.reader.at_eof():
                chunk = await self.reader.read(1024)
                if not chunk:
                    break
                buffer.extend(chunk)

                # Processa todos os pacotes completos no buffer
                while len(buffer) >= 5:
                    # Encontra o cabeçalho 0x78 0x78
                    header_pos = buffer.find(b"\x78\x78")
                    if header_pos == -1:
                        # Se não encontrar 0x78 0x78, descarta lixo
                        buffer.clear()
                        break
                    if header_pos > 0:
                        del buffer[:header_pos]

                    if len(buffer) < 4:
                        break

                    length = buffer[2]
                    total_packet_len = length + 5  # 2 start + 1 len + length + 2 stop

                    if len(buffer) < total_packet_len:
                        break

                    packet = bytes(buffer[:total_packet_len])
                    del buffer[:total_packet_len]

                    await self._processar_pacote(packet)
        except Exception as e:
            print(f"⚠️ [EMED-GPS] Erro na sessão {self.addr}: {e}")
        finally:
            self.writer.close()
            await self.writer.wait_closed()
            print(f"🔌 [EMED-GPS] Conexão encerrada: {self.addr}")

    async def _processar_pacote(self, packet: bytes):
        if len(packet) < 6:
            return
        proto = packet[3]

        # 1. Login do Rastreador (0x01)
        if proto == 0x01:
            imei_bytes = packet[4:12]
            # O IMEI vem codificado em BCD (8 bytes = 16 dígitos)
            raw_imei = "".join(f"{b:02x}" for b in imei_bytes)
            # Remove o zero à esquerda comum em IMEIs de 15 dígitos
            self.imei = raw_imei.lstrip("0") if raw_imei.startswith("0") and len(raw_imei) == 16 else raw_imei
            serial_bytes = packet[12:14]

            print(f"🔐 [EMED-GPS] LOGIN CONFIRMADO! Rastreador IMEI: {self.imei}")

            # Busca se há veículo cadastrado com esse IMEI
            try:
                with sqlite3.connect(self.db_name, timeout=10.0) as conn:
                    conn.execute("PRAGMA journal_mode=WAL;")
                    conn.execute("PRAGMA busy_timeout=10000;")
                    cur = conn.cursor()
                    cur.execute("SELECT placa, modelo, km_atual, condutor_atual FROM veiculos WHERE imei = ?", (self.imei,))
                    row = cur.fetchone()
                    if row:
                        self.placa = row[0]
                        print(f"🚗 [EMED-GPS] Veículo Vinculado: {row[1]} (Placa {row[0]}) | Odômetro: {row[2]} KM | Condutor: {row[3]}")
                    else:
                        print(f"ℹ️ [EMED-GPS] IMEI {self.imei} não cadastrado na base, vinculando à placa padrão {self.placa}")
            except Exception as e:
                print(f"Aviso no banco: {e}")

            # Envia resposta obrigatória de Login ACK
            ack = gerar_pacote_ack(0x01, serial_bytes)
            self.writer.write(ack)
            await self.writer.drain()
            print(f"✅ [EMED-GPS] Login ACK enviado ao J16 com sucesso!")

        # 2. Pacote de Localização / Telemetria GPS (0x12 ou 0x22)
        elif proto in (0x12, 0x22):
            try:
                # Data / Hora (UTC)
                yy = 2000 + packet[4]
                mm = packet[5]
                dd = packet[6]
                hh = packet[7]
                mi = packet[8]
                ss = packet[9]
                dt_utc = datetime.datetime(yy, mm, dd, hh, mi, ss, tzinfo=datetime.timezone.utc)
                # Converte para horário de Brasília (UTC-3)
                dt_br = dt_utc - datetime.timedelta(hours=3)
                dt_str = dt_br.strftime("%d/%m/%Y %H:%M")

                # Quantidade de satélites
                sat_byte = packet[10]
                sat_count = sat_byte & 0x0F

                # Latitude (4 bytes) e Longitude (4 bytes)
                raw_lat = struct.unpack(">I", packet[11:15])[0]
                raw_lon = struct.unpack(">I", packet[15:19])[0]
                lat = round(raw_lat / 1800000.0, 6)
                lon = round(raw_lon / 1800000.0, 6)

                # Velocidade (1 byte em km/h)
                vel = packet[19]

                # Status e Rumo (2 bytes)
                course_status = struct.unpack(">H", packet[20:22])[0]
                is_south = (course_status & 0x0400) == 0  # Bit 10: 1=N, 0=S
                is_west = (course_status & 0x0800) != 0   # Bit 11: 1=W, 0=E
                if (is_south or lat <= 35.0) and lat > 0:
                    lat = -lat
                if (is_west or (30.0 <= lon <= 75.0)) and lon > 0:
                    lon = -lon

                print(f"📍 [EMED-GPS] {dt_str} | Satélites: {sat_count} | Lat: {lat}, Lon: {lon} | Vel: {vel} km/h")

                # Sincroniza com a tabela oficial de veículos e viagens da EMED
                payload_telemetria = {
                    "placa": self.placa,
                    "imei": self.imei or "",
                    "latitude": lat,
                    "longitude": lon,
                    "velocidade_kmh": vel,
                    "data_inicio": dt_str,
                    "data_fim": dt_str,
                    "acao": "ATUALIZAR_TELEMETRIA",
                }
                res = registrar_telemetria_ou_viagem_gps(self.db_name, payload_telemetria)
                print(f"🏁 [EMED-GPS] Banco Atualizado! KM Atual: {res.get('km_atual')} | Condutor ao Volante: {res.get('condutor')}")
            except Exception as e:
                print(f"⚠️ [EMED-GPS] Erro ao decodificar telemetria GPS: {e}")

        # 3. Heartbeat / Status de Ignição e Bateria (0x13)
        elif proto == 0x13:
            serial_bytes = packet[9:11] if len(packet) >= 13 else bytes([0x00, 0x01])
            # Envia ACK do Heartbeat para manter a conexão aberta
            ack = gerar_pacote_ack(0x13, serial_bytes)
            self.writer.write(ack)
            await self.writer.drain()
            print(f"💓 [EMED-GPS] Heartbeat recebido e ACK confirmado.")

async def main(host: str = "0.0.0.0", port: int = 5023, db_name: str = "emed.db"):
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), db_name)
    print("=======================================================================")
    print("  EMED ELETROMEDICINA — RECEPTOR TCP NATIVO DE TELEMETRIA GPS (J16 4G) ")
    print("=======================================================================")
    print(f"📡 Ouvindo na porta TCP: {port} (Host: {host})")
    print(f"💾 Banco de dados: {db_path}")
    print("=======================================================================\n")

    async def handle_client(reader, writer):
        session = GT06ClientSession(reader, writer, db_path)
        await session.run()

    server = await asyncio.start_server(handle_client, host, port)
    async with server:
        await server.serve_forever()

if __name__ == "__main__":
    porta = int(sys.argv[1]) if len(sys.argv) > 1 else 5023
    asyncio.run(main(port=porta))
