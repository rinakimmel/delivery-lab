from typing import Optional
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

app = FastAPI()

# מסד נתונים בזיכרון ומונה מזהים
deliveries: dict[int, dict] = {}
next_id: int = 1

VALID_STATUSES = ["created", "in_transit", "delivered"]


# התאמת שגיאות לפורמט הנדרש במטלה: {"error": "..."}
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": str(exc.detail)}
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # החזרת קוד 400 עבור שגיאות ולידציה במקום 422
    return JSONResponse(
        status_code=400,
        content={"error": "Invalid request body"}
    )


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/deliveries", status_code=201)
async def create_delivery(request: Request):
    global next_id

    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON or empty body")

    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Body must be a JSON object")

    recipient = data.get("recipient")
    address = data.get("address")

    if not isinstance(recipient, str) or not recipient.strip():
        raise HTTPException(status_code=400, detail="Recipient must be a non-empty string")
    if not isinstance(address, str) or not address.strip():
        raise HTTPException(status_code=400, detail="Address must be a non-empty string")

    delivery_id = next_id
    next_id += 1

    delivery = {
        "id": delivery_id,
        "recipient": recipient,
        "address": address,
        "status": "created"
    }
    deliveries[delivery_id] = delivery
    return delivery


@app.get("/deliveries")
def list_deliveries(status: Optional[str] = None):
    if status is not None:
        if status not in VALID_STATUSES:
            raise HTTPException(status_code=400, detail="Unknown status filter")
        return [d for d in deliveries.values() if d["status"] == status]
    return list(deliveries.values())


@app.get("/deliveries/{delivery_id}")
def get_delivery(delivery_id: int):
    if delivery_id not in deliveries:
        raise HTTPException(status_code=404, detail="Delivery not found")
    return deliveries[delivery_id]


@app.patch("/deliveries/{delivery_id}/status")
async def update_status(delivery_id: int, request: Request):
    if delivery_id not in deliveries:
        raise HTTPException(status_code=404, detail="Delivery not found")

    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    if not isinstance(data, dict) or "status" not in data:
        raise HTTPException(status_code=400, detail="Missing status field")

    new_status = data["status"]
    if new_status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail="Unknown status")

    current_status = deliveries[delivery_id]["status"]

    # חוקי מעבר סטטוס: created -> in_transit -> delivered
    valid_transitions = {
        "created": "in_transit",
        "in_transit": "delivered",
        "delivered": None
    }

    if new_status == current_status:
        raise HTTPException(status_code=409, detail="Status is already set to this value")

    if valid_transitions.get(current_status) != new_status:
        raise HTTPException(status_code=409, detail=f"Cannot transition from {current_status} to {new_status}")

    deliveries[delivery_id]["status"] = new_status
    return deliveries[delivery_id]


@app.delete("/deliveries/{delivery_id}", status_code=204)
def delete_delivery(delivery_id: int):
    if delivery_id not in deliveries:
        raise HTTPException(status_code=404, detail="Delivery not found")

    if deliveries[delivery_id]["status"] != "created":
        raise HTTPException(status_code=409, detail="Can only delete deliveries with status 'created'")

    del deliveries[delivery_id]
    return Response(status_code=204)