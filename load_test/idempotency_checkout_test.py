import time
import uuid
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

BASE_URL = "http://localhost:8000"
EVENT_NAME = f"Evento Idempotencia {uuid.uuid4().hex[:6]}"
TOTAL_TICKETS = 5
USER_ID = "andre"
QUANTITY = 1

TOTAL_CHECKOUT_REQUESTS = 20
MAX_WORKERS = 10
IDEMPOTENCY_KEY = f"checkout-{USER_ID}-same-key-001"


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
    data = response.json()
    return data["id"]


def create_reservation(event_id: int) -> int:
    response = requests.post(
        f"{BASE_URL}/reservations",
        json={
            "event_id": event_id,
            "user_id": USER_ID,
            "quantity": QUANTITY,
        },
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()
    return data["reservation_id"]


def get_stock(event_id: int) -> dict:
    response = requests.get(f"{BASE_URL}/events/{event_id}/stock", timeout=10)
    response.raise_for_status()
    return response.json()


def get_order(order_id: int) -> dict:
    response = requests.get(f"{BASE_URL}/checkout/orders/{order_id}", timeout=10)
    response.raise_for_status()
    return response.json()


def do_checkout(reservation_id: int, request_index: int) -> dict:
    try:
        response = requests.post(
            f"{BASE_URL}/checkout",
            json={
                "reservation_id": reservation_id,
                "user_id": USER_ID,
            },
            headers={
                "Idempotency-Key": IDEMPOTENCY_KEY,
                "Content-Type": "application/json",
            },
            timeout=10,
        )

        try:
            body = response.json()
        except Exception:
            body = response.text

        return {
            "request_index": request_index,
            "status_code": response.status_code,
            "body": body,
        }
    except Exception as exc:
        return {
            "request_index": request_index,
            "status_code": "EXCEPTION",
            "body": str(exc),
        }


def main():
    print("Criando evento...")
    event_id = create_event()
    print(f"Evento criado: {event_id}")

    print("Criando reserva...")
    reservation_id = create_reservation(event_id)
    print(f"Reserva criada: {reservation_id}")

    stock_before_checkout = get_stock(event_id)
    print(f"Estoque antes do checkout: {stock_before_checkout}")

    print("-" * 70)
    print(f"Disparando {TOTAL_CHECKOUT_REQUESTS} checkouts concorrentes")
    print(f"Todos com a mesma Idempotency-Key: {IDEMPOTENCY_KEY}")
    print("-" * 70)

    start = time.perf_counter()
    results = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [
            executor.submit(do_checkout, reservation_id, i)
            for i in range(TOTAL_CHECKOUT_REQUESTS)
        ]

        for future in as_completed(futures):
            results.append(future.result())

    elapsed = time.perf_counter() - start

    counter = Counter(str(result["status_code"]) for result in results)
    print(f"Tempo total: {elapsed:.2f}s")
    print(f"Contagem por status: {dict(counter)}")

    success_results = [r for r in results if r["status_code"] == 200]
    exception_results = [r for r in results if r["status_code"] == "EXCEPTION"]
    other_results = [
        r for r in results if r["status_code"] not in (200, "EXCEPTION")
    ]

    print(f"Sucessos: {len(success_results)}")
    print(f"Exceções: {len(exception_results)}")
    print(f"Outros status: {len(other_results)}")
    print("-" * 70)

    if success_results:
        print("Exemplos de respostas:")
        for item in success_results[:5]:
            print(item)

    if exception_results:
        print("-" * 70)
        print("Exceções:")
        for item in exception_results[:5]:
            print(item)

    if other_results:
        print("-" * 70)
        print("Outros status inesperados:")
        for item in other_results[:10]:
            print(item)

    order_ids = set()
    returned_keys = set()

    for result in success_results:
        body = result["body"]
        if isinstance(body, dict):
            order_id = body.get("order_id")
            idem_key = body.get("idempotency_key")
            if order_id is not None:
                order_ids.add(order_id)
            if idem_key is not None:
                returned_keys.add(idem_key)

    print("-" * 70)
    print("Validação de idempotência:")
    print(f"Order IDs retornados: {order_ids}")
    print(f"Quantidade de order IDs distintos: {len(order_ids)}")
    print(f"Idempotency keys retornadas: {returned_keys}")

    if len(order_ids) == 1:
        print("OK: apenas uma order foi criada/retornada.")
        only_order_id = next(iter(order_ids))
        print(f"Order final: {get_order(only_order_id)}")
    else:
        print("FALHA: mais de uma order foi retornada para a mesma Idempotency-Key.")

    stock_after_checkout = get_stock(event_id)
    print("-" * 70)
    print(f"Estoque depois do checkout: {stock_after_checkout}")
    print("Observação: o estoque já foi reduzido na reserva, não no checkout.")


if __name__ == "__main__":
    main()