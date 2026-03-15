import time
import uuid
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

BASE_URL = "http://localhost:8000"
EVENT_ID = 1
TOTAL_REQUESTS = 100
MAX_WORKERS = 30
QUANTITY_PER_REQUEST = 1


def get_stock():
    response = requests.get(f"{BASE_URL}/events/{EVENT_ID}/stock", timeout=10)
    response.raise_for_status()
    return response.json()


def try_reserve(index: int) -> dict:
    user_id = f"user-{index}-{uuid.uuid4().hex[:6]}"

    payload = {
        "event_id": EVENT_ID,
        "user_id": user_id,
        "quantity": QUANTITY_PER_REQUEST
    }

    try:
        response = requests.post(
            f"{BASE_URL}/reservations",
            json=payload,
            timeout=10
        )

        try:
            body = response.json()
        except Exception:
            body = response.text

        return {
            "user_id": user_id,
            "status_code": response.status_code,
            "body": body
        }

    except Exception as exc:
        return {
            "user_id": user_id,
            "status_code": "EXCEPTION",
            "body": str(exc)
        }


def main():
    stock_before = get_stock()

    print("Iniciando teste de concorrência...")
    print(f"Estoque antes: {stock_before}")
    print("-" * 60)

    start = time.perf_counter()
    results = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(try_reserve, i) for i in range(TOTAL_REQUESTS)]

        for future in as_completed(futures):
            results.append(future.result())

    elapsed = time.perf_counter() - start

    stock_after = get_stock()

    counter = Counter(str(result["status_code"]) for result in results)

    success_results = [r for r in results if r["status_code"] == 200]
    conflict_results = [r for r in results if r["status_code"] == 409]
    exception_results = [r for r in results if r["status_code"] == "EXCEPTION"]
    other_results = [
        r for r in results
        if r["status_code"] not in (200, 409, "EXCEPTION")
    ]

    print("Resumo:")
    print(f"Tempo total: {elapsed:.2f}s")
    print(f"Contagem por status: {dict(counter)}")
    print(f"Sucessos: {len(success_results)}")
    print(f"Conflitos: {len(conflict_results)}")
    print(f"Exceções: {len(exception_results)}")
    print(f"Outros: {len(other_results)}")
    print("-" * 60)
    print(f"Estoque antes: {stock_before}")
    print(f"Estoque depois: {stock_after}")
    print("-" * 60)

    total_reserved = len(success_results) * QUANTITY_PER_REQUEST
    print(f"Total reservado com sucesso: {total_reserved}")

    before_available = stock_before["available_tickets"]
    after_available = stock_after["available_tickets"]
    expected_after = max(before_available - total_reserved, 0)

    print(f"Estoque esperado após teste: {expected_after}")
    print(f"Estoque real após teste: {after_available}")

    if after_available == expected_after:
        print("Validação OK: sem indício de overselling.")
    else:
        print("Atenção: divergência entre esperado e real.")


if __name__ == "__main__":
    main()