import time
import uuid
from collections import Counter

import requests

BASE_URL = "http://localhost:8000"
EVENT_NAME = f"Evento Fila Virtual {uuid.uuid4().hex[:6]}"
TOTAL_TICKETS = 10

USERS = [
    "user_1",
    "user_2",
    "user_3",
    "user_4",
    "user_5",
]


def create_event() -> int:
    response = requests.post(
        f"{BASE_URL}/events",
        json={
            "name": EVENT_NAME,
            "total_tickets": TOTAL_TICKETS,
        },
        timeout=10,
    )
    response.raise_for_status()
    return response.json()["id"]


def join_queue(event_id: int, user_id: str) -> dict:
    response = requests.post(
        f"{BASE_URL}/queue/join",
        json={
            "event_id": event_id,
            "user_id": user_id,
        },
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def get_queue_status(event_id: int, queue_token: str) -> dict:
    response = requests.get(
        f"{BASE_URL}/queue/{event_id}/{queue_token}",
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def reserve_ticket(event_id: int, user_id: str, queue_token: str) -> dict:
    response = requests.post(
        f"{BASE_URL}/reservations",
        json={
            "event_id": event_id,
            "user_id": user_id,
            "quantity": 1,
            "queue_token": queue_token,
        },
        timeout=10,
    )

    try:
        body = response.json()
    except Exception:
        body = response.text

    return {
        "status_code": response.status_code,
        "body": body,
    }


def print_statuses(title: str, statuses: dict):
    print("-" * 80)
    print(title)
    print("-" * 80)
    for user_id, status_data in statuses.items():
        print(
            f"user={user_id} | "
            f"status={status_data['status']} | "
            f"position={status_data.get('position')} | "
            f"expires_at={status_data.get('expires_at')}"
        )


def collect_statuses(event_id: int, joined_users: list[dict]) -> dict:
    result = {}
    for item in joined_users:
        status = get_queue_status(event_id, item["queue_token"])
        result[item["user_id"]] = status
    return result


def main():
    print("Criando evento...")
    event_id = create_event()
    print(f"Evento criado: {event_id}")

    joined_users = []

    print("\nUsuários entrando na fila...")
    for user_id in USERS:
        queue_data = join_queue(event_id, user_id)
        joined_users.append(
            {
                "user_id": user_id,
                "queue_token": queue_data["queue_token"],
            }
        )
        print(
            f"user={user_id} entrou | "
            f"token={queue_data['queue_token']} | "
            f"status={queue_data['status']} | "
            f"position={queue_data['position']}"
        )

    print("\nAguardando dispatcher liberar usuários...")
    time.sleep(3)

    statuses = collect_statuses(event_id, joined_users)
    print_statuses("Status após primeira liberação", statuses)

    counter = Counter(status["status"] for status in statuses.values())
    print("\nResumo de status:")
    print(dict(counter))

    ready_users = [
        {
            "user_id": item["user_id"],
            "queue_token": item["queue_token"],
        }
        for item in joined_users
        if statuses[item["user_id"]]["status"] == "READY"
    ]

    waiting_users = [
        {
            "user_id": item["user_id"],
            "queue_token": item["queue_token"],
        }
        for item in joined_users
        if statuses[item["user_id"]]["status"] == "WAITING"
    ]

    if waiting_users:
        print("\nTestando tentativa indevida de reserva por usuário WAITING...")
        invalid_waiting = waiting_users[0]
        invalid_result = reserve_ticket(
            event_id=event_id,
            user_id=invalid_waiting["user_id"],
            queue_token=invalid_waiting["queue_token"],
        )
        print(
            f"Reserva user WAITING={invalid_waiting['user_id']} -> "
            f"status_code={invalid_result['status_code']} | "
            f"body={invalid_result['body']}"
        )

    print(f"\nREADY inicialmente: {[u['user_id'] for u in ready_users]}")
    print(f"WAITING inicialmente: {[u['user_id'] for u in waiting_users]}")

    if ready_users:
        first_ready = ready_users[0]
        print("\nConsumindo um slot READY com reserva...")
        reserve_result = reserve_ticket(
            event_id=event_id,
            user_id=first_ready["user_id"],
            queue_token=first_ready["queue_token"],
        )
        print(
            f"Reserva user={first_ready['user_id']} -> "
            f"status_code={reserve_result['status_code']} | "
            f"body={reserve_result['body']}"
        )

    print("\nAguardando dispatcher preencher slot liberado...")
    time.sleep(3)

    statuses_after_reservation = collect_statuses(event_id, joined_users)
    print_statuses(
        "Status após um usuário READY consumir a vez",
        statuses_after_reservation
    )

    counter_after_reservation = Counter(
        status["status"] for status in statuses_after_reservation.values()
    )
    print("\nResumo após reserva:")
    print(dict(counter_after_reservation))

    still_waiting = [
        {
            "user_id": item["user_id"],
            "queue_token": item["queue_token"],
        }
        for item in joined_users
        if statuses_after_reservation[item["user_id"]]["status"] == "WAITING"
    ]

    if still_waiting:
        print("\nAgora vamos testar expiração natural dos slots READY remanescentes.")
        print("Aguardando a janela de compra expirar...")
        time.sleep(20)

        statuses_after_expiration = collect_statuses(event_id, joined_users)
        print_statuses(
            "Status após expiração da janela READY",
            statuses_after_expiration
        )

        counter_after_expiration = Counter(
            status["status"] for status in statuses_after_expiration.values()
        )
        print("\nResumo após expiração:")
        print(dict(counter_after_expiration))

    print("\nTeste concluído.")
    print("\nValidações esperadas:")
    print("1. Inicialmente apenas QUEUE_MAX_ACTIVE_USERS devem ficar READY.")
    print("2. Após uma reserva consumir o slot, outro WAITING deve virar READY.")
    print("3. Após expiração da janela READY, novos usuários podem ser promovidos.")
    print("4. Apenas usuários READY conseguem reservar.")


if __name__ == "__main__":
    main()