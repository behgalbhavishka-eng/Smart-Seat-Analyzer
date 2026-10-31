
from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
from pathlib import Path
from datetime import datetime

app = Flask(__name__)
app.secret_key = "smart-seat-local-demo-key"

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "smart_seats.db"


# --------------------------------------------------
# DATABASE CONNECTION
# --------------------------------------------------

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# --------------------------------------------------
# DATABASE INITIALIZATION
# --------------------------------------------------

def init_db():
    conn = get_db()

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            venue TEXT NOT NULL,
            event_date TEXT NOT NULL,
            total_seats INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS seats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            seat_number TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Available',
            FOREIGN KEY (event_id) REFERENCES events(id)
                ON DELETE CASCADE,
            UNIQUE(event_id, seat_number)
        );

        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            seat_id INTEGER NOT NULL,
            attendee_name TEXT NOT NULL,
            email TEXT NOT NULL,
            booked_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Confirmed',
            FOREIGN KEY (event_id) REFERENCES events(id),
            FOREIGN KEY (seat_id) REFERENCES seats(id)
        );
    """)

    # Migration: preserve an existing database and add status
    # if the bookings table was created by an older version.
    columns = conn.execute(
        "PRAGMA table_info(bookings)"
    ).fetchall()

    column_names = [column["name"] for column in columns]

    if "status" not in column_names:
        conn.execute("""
            ALTER TABLE bookings
            ADD COLUMN status TEXT NOT NULL DEFAULT 'Confirmed'
        """)

    # Create a sample event only when no event exists.
    event = conn.execute(
        "SELECT id FROM events LIMIT 1"
    ).fetchone()

    if event is None:
        cursor = conn.execute("""
            INSERT INTO events (name, venue, event_date, total_seats)
            VALUES (?, ?, ?, ?)
        """, (
            "TechFest 2026",
            "Main Auditorium",
            "2026-11-15",
            60
        ))

        event_id = cursor.lastrowid

        for row in range(6):
            for col in range(1, 11):
                seat_number = f"{chr(65 + row)}{col:02d}"

                conn.execute("""
                    INSERT INTO seats (event_id, seat_number, status)
                    VALUES (?, ?, 'Available')
                """, (event_id, seat_number))

    conn.commit()
    conn.close()


# --------------------------------------------------
# EVENT STATISTICS
# --------------------------------------------------

def get_event_stats(conn, event_id):
    event = conn.execute(
        "SELECT * FROM events WHERE id = ?",
        (event_id,)
    ).fetchone()

    if event is None:
        return None

    counts = conn.execute("""
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN status = 'Available'
                THEN 1 ELSE 0 END) AS available,
            SUM(CASE WHEN status = 'Booked'
                THEN 1 ELSE 0 END) AS booked,
            SUM(CASE WHEN status = 'Unavailable'
                THEN 1 ELSE 0 END) AS unavailable
        FROM seats
        WHERE event_id = ?
    """, (event_id,)).fetchone()

    return {
        "event": event,
        "total": counts["total"] or 0,
        "available": counts["available"] or 0,
        "booked": counts["booked"] or 0,
        "unavailable": counts["unavailable"] or 0
    }


# --------------------------------------------------
# DASHBOARD
# --------------------------------------------------

@app.route("/")
def index():
    conn = get_db()

    events = conn.execute("""
        SELECT * FROM events
        ORDER BY id DESC
    """).fetchall()

    dashboard = []

    for event in events:
        stats = get_event_stats(conn, event["id"])
        dashboard.append(stats)

    # Count only active bookings on the dashboard.
    total_bookings = conn.execute("""
        SELECT COUNT(*) FROM bookings
        WHERE status = 'Confirmed'
    """).fetchone()[0]

    conn.close()

    return render_template(
        "index.html",
        dashboard=dashboard,
        total_bookings=total_bookings
    )


# --------------------------------------------------
# CREATE EVENT
# --------------------------------------------------

@app.route("/events/create", methods=["POST"])
def create_event():
    name = request.form.get("name", "").strip()
    venue = request.form.get("venue", "").strip()
    event_date = request.form.get("event_date", "").strip()

    try:
        total_seats = int(request.form.get("total_seats", "0"))
    except ValueError:
        total_seats = 0

    if not name or not venue or not event_date:
        flash("Please fill in all event details.", "error")
        return redirect(url_for("index"))

    try:
        datetime.strptime(event_date, "%Y-%m-%d")
    except ValueError:
        flash("Please enter a valid event date.", "error")
        return redirect(url_for("index"))

    if not 1 <= total_seats <= 500:
        flash("Seat capacity must be between 1 and 500.", "error")
        return redirect(url_for("index"))

    conn = get_db()

    cursor = conn.execute("""
        INSERT INTO events (name, venue, event_date, total_seats)
        VALUES (?, ?, ?, ?)
    """, (name, venue, event_date, total_seats))

    event_id = cursor.lastrowid

    for number in range(1, total_seats + 1):
        seat_number = f"S{number:03d}"

        conn.execute("""
            INSERT INTO seats (event_id, seat_number, status)
            VALUES (?, ?, 'Available')
        """, (event_id, seat_number))

    conn.commit()
    conn.close()

    flash("Event created successfully!", "success")
    return redirect(url_for("index"))


# --------------------------------------------------
# SEAT LAYOUT
# --------------------------------------------------

@app.route("/seats")
def seats():
    conn = get_db()

    events = conn.execute("""
        SELECT * FROM events
        ORDER BY id DESC
    """).fetchall()

    if not events:
        conn.close()
        flash("Please create an event first.", "error")
        return redirect(url_for("index"))

    try:
        event_id = int(
            request.args.get("event_id", events[0]["id"])
        )
    except (ValueError, TypeError):
        conn.close()
        flash("Please select a valid event.", "error")
        return redirect(url_for("index"))

    event = conn.execute("""
        SELECT * FROM events WHERE id = ?
    """, (event_id,)).fetchone()

    if event is None:
        conn.close()
        flash("Event not found.", "error")
        return redirect(url_for("index"))

    seat_rows = conn.execute("""
        SELECT * FROM seats
        WHERE event_id = ?
        ORDER BY id
    """, (event_id,)).fetchall()

    stats = get_event_stats(conn, event_id)
    conn.close()

    return render_template(
        "seats.html",
        events=events,
        event=event,
        seats=seat_rows,
        stats=stats
    )


# --------------------------------------------------
# BOOK A SEAT
# --------------------------------------------------

@app.route("/book", methods=["POST"])
def book():
    event_id = request.form.get("event_id", type=int)
    seat_id = request.form.get("seat_id", type=int)
    attendee_name = request.form.get(
        "attendee_name", ""
    ).strip()
    email = request.form.get("email", "").strip()

    if not event_id or not attendee_name or not email:
        flash("Please enter your name and email.", "error")

        if event_id:
            return redirect(url_for("seats", event_id=event_id))

        return redirect(url_for("index"))

    conn = get_db()

    try:
        # Manual seat selection.
        if seat_id:
            seat = conn.execute("""
                SELECT * FROM seats
                WHERE id = ? AND event_id = ?
            """, (seat_id, event_id)).fetchone()

        # Automatically choose the next available seat.
        else:
            seat = conn.execute("""
                SELECT * FROM seats
                WHERE event_id = ?
                  AND status = 'Available'
                ORDER BY id
                LIMIT 1
            """, (event_id,)).fetchone()

        if seat is None or seat["status"] != "Available":
            conn.close()
            flash(
                "This seat is not available. Please choose another.",
                "error"
            )
            return redirect(url_for("seats", event_id=event_id))

        # Insert the booking as a confirmed record.
        conn.execute("""
            INSERT INTO bookings
                (event_id, seat_id, attendee_name, email,
                 booked_at, status)
            VALUES (?, ?, ?, ?, ?, 'Confirmed')
        """, (
            event_id,
            seat["id"],
            attendee_name,
            email,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))

        # Reserve the seat only if it is still available.
        update = conn.execute("""
            UPDATE seats
            SET status = 'Booked'
            WHERE id = ? AND status = 'Available'
        """, (seat["id"],))

        if update.rowcount != 1:
            conn.rollback()
            flash(
                "The seat is no longer available. Please try again.",
                "error"
            )
        else:
            conn.commit()
            flash(
                f"Booking successful! Your seat is {seat['seat_number']}.",
                "success"
            )

    except sqlite3.Error:
        conn.rollback()
        flash(
            "Booking could not be completed. Please try again.",
            "error"
        )

    finally:
        conn.close()

    return redirect(url_for("seats", event_id=event_id))


# --------------------------------------------------
# BOOKING HISTORY AND SEARCH
# --------------------------------------------------

@app.route("/bookings")
def bookings():
    search = request.args.get("search", "").strip()

    conn = get_db()

    records = conn.execute("""
        SELECT
            bookings.*,
            events.name AS event_name,
            seats.seat_number
        FROM bookings
        JOIN events
            ON events.id = bookings.event_id
        JOIN seats
            ON seats.id = bookings.seat_id
        WHERE bookings.attendee_name LIKE ?
           OR bookings.email LIKE ?
           OR events.name LIKE ?
        ORDER BY bookings.id DESC
    """, (
        f"%{search}%",
        f"%{search}%",
        f"%{search}%"
    )).fetchall()

    conn.close()

    return render_template(
        "bookings.html",
        bookings=records,
        search=search
    )


# --------------------------------------------------
# CANCEL BOOKING WITHOUT DELETING HISTORY
# --------------------------------------------------

@app.route("/cancel/<int:booking_id>", methods=["POST"])
def cancel_booking(booking_id):
    conn = get_db()

    try:
        booking = conn.execute("""
            SELECT * FROM bookings
            WHERE id = ?
        """, (booking_id,)).fetchone()

        if booking is None:
            flash("Booking not found.", "error")

        elif booking["status"] == "Cancelled":
            flash(
                "This booking has already been cancelled.",
                "error"
            )

        else:
            # Keep the booking record and update its status.
            conn.execute("""
                UPDATE bookings
                SET status = 'Cancelled'
                WHERE id = ?
            """, (booking_id,))

            # Release the seat for another attendee.
            conn.execute("""
                UPDATE seats
                SET status = 'Available'
                WHERE id = ?
            """, (booking["seat_id"],))

            conn.commit()

            flash(
                "Booking cancelled. The record remains in history.",
                "success"
            )

    except sqlite3.Error:
        conn.rollback()
        flash(
            "Cancellation failed. Please try again.",
            "error"
        )

    finally:
        conn.close()

    return redirect(url_for("bookings"))


# --------------------------------------------------
# AVAILABILITY STATISTICS API
# --------------------------------------------------

@app.route("/api/stats/<int:event_id>")
def api_stats(event_id):
    conn = get_db()
    stats = get_event_stats(conn, event_id)
    conn.close()

    if stats is None:
        return {"error": "Event not found"}, 404

    return {
        "total": stats["total"],
        "available": stats["available"],
        "booked": stats["booked"],
        "unavailable": stats["unavailable"]
    }


# --------------------------------------------------
# START APPLICATION
# --------------------------------------------------

init_db()

if __name__ == "__main__":
    app.run(debug=True)
