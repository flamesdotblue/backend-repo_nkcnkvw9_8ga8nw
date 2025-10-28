import os
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from typing import Dict, Any

from schemas import Booking
from database import create_document

app = FastAPI(title="Alankritha Naturals API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI Backend!"}

@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}

@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    
    try:
        # Try to import database module
        from database import db
        
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            
            # Try to list collections to verify connectivity
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]  # Show first 10 collections
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
            
    except ImportError:
        response["database"] = "❌ Database module not found (run enable-database first)"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"
    
    # Check environment variables
    import os
    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    
    return response


def build_ics(booking: Booking) -> str:
    """Generate a simple ICS calendar event string for the booking."""
    start = booking.preferred_datetime
    end = start + timedelta(hours=1)
    start_str = start.strftime('%Y%m%dT%H%M%S')
    end_str = end.strftime('%Y%m%dT%H%M%S')
    now_str = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
    uid = f"booking-{start_str}-{booking.email}"
    summary = f"Appointment: {booking.service} - Alankritha Naturals"
    description = f"Name: {booking.name}\\nPhone: {booking.phone}\\nNotes: {booking.notes or ''}"
    location = "Alankritha Naturals, Hyderabad"

    ics = (
        "BEGIN:VCALENDAR\n"
        "VERSION:2.0\n"
        "PRODID:-//Alankritha Naturals//Booking//EN\n"
        "BEGIN:VEVENT\n"
        f"UID:{uid}\n"
        f"DTSTAMP:{now_str}\n"
        f"DTSTART:{start_str}\n"
        f"DTEND:{end_str}\n"
        f"SUMMARY:{summary}\n"
        f"DESCRIPTION:{description}\n"
        f"LOCATION:{location}\n"
        "END:VEVENT\n"
        "END:VCALENDAR\n"
    )
    return ics

@app.post("/api/book")
async def create_booking(payload: Dict[str, Any]):
    """
    Create a booking document and return success state with optional ICS content.
    Expects ISO datetime string for preferred_datetime.
    """
    try:
        # Convert preferred_datetime to datetime if provided as string
        if isinstance(payload.get("preferred_datetime"), str):
            try:
                payload["preferred_datetime"] = datetime.fromisoformat(payload["preferred_datetime"])  # type: ignore
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid preferred_datetime format. Use ISO 8601.")

        booking = Booking(**payload)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.errors())

    try:
        booking_id = create_document("booking", booking)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    # Build ICS for download
    ics = build_ics(booking)
    return JSONResponse({
        "status": "success",
        "message": "Appointment confirmed — we’ll call to confirm the time.",
        "booking_id": booking_id,
        "ics": ics,
    })


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
