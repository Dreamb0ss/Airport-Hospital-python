"""Airport Management System based on the airport UML diagram."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal


class Airport:
    def __init__(
        self, iata_code: str, name: str, city: str, first_gate_code: str, terminal: str
    ):
        self._iata_code = iata_code
        self._name = name
        self._city = city
        self._gates: dict[str, Gate] = {}
        self._departures: list[Flight] = []
        self._claims: dict[str, BaggageClaim] = {}
        self.add_gate(first_gate_code, terminal)

    def add_gate(self, gate_code: str, terminal: str) -> Gate:
        if gate_code in self._gates:
            raise ValueError(f"Gate {gate_code} already exists at this airport.")
        gate = Gate(gate_code, terminal, self)
        self._gates[gate_code] = gate
        return gate

    def plan_flight(self, flight: Flight) -> None:
        if flight._origin is not self:
            raise ValueError("Plan the departure at the flight's origin airport.")
        if flight not in self._departures:
            self._departures.append(flight)

    def assign_gate(self, flight: Flight, gate_code: str | None = None) -> Gate:
        if flight not in self._departures:
            raise ValueError("Plan the flight at this airport before assigning its gate.")
        if gate_code is None:
            gate_code = next(iter(self._gates))
        if gate_code not in self._gates:
            raise ValueError(f"Gate {gate_code} is unavailable at this airport.")
        gate = self._gates[gate_code]
        flight._gate = gate
        return gate


class Gate:
    def __init__(self, gate_code: str, terminal: str, airport: Airport):
        self._gate_code = gate_code
        self._terminal = terminal
        self._status = "Closed"
        self._airport = airport

    def open(self) -> None:
        self._status = "Open"

    def close(self) -> None:
        self._status = "Closed"


class Aircraft:
    def __init__(self, registration: str, model: str, seat_capacity: int):
        if seat_capacity < 1:
            raise ValueError("The aircraft must have at least one seat.")
        self._registration = registration
        self._model = model
        self._seat_capacity = seat_capacity
        self._check_pending = False

    def is_available(self) -> bool:
        return not self._check_pending

    def schedule_check(self) -> None:
        self._check_pending = True

    def complete_check(self) -> None:
        self._check_pending = False


class Flight:
    def __init__(
        self, flight_number: str, departure_at: datetime, origin: Airport, destination: Airport
    ):
        self._flight_number = flight_number
        self._departure_at = departure_at
        self._status = "Scheduled"
        self._origin = origin
        self._destination = destination
        self._gate: Gate | None = None
        self._aircraft: Aircraft | None = None
        self._tickets: list[Ticket] = []

    def set_status(self, status: str) -> None:
        if status == "Boarding":
            self.open_boarding()
            return
        if status not in {"Scheduled", "Delayed", "Departed", "Cancelled"}:
            raise ValueError("Use a valid flight status.")
        if self._status in {"Departed", "Cancelled"} and status != self._status:
            raise ValueError(f"This flight is already {self._status.lower()}.")
        self._status = status

    def open_boarding(self) -> None:
        if self._status in {"Departed", "Cancelled"}:
            raise ValueError(f"This flight is already {self._status.lower()}.")
        if not self._ready_for_boarding():
            raise ValueError("Boarding requires an open gate and an available aircraft.")
        self._status = "Boarding"

    def assign_aircraft(self, aircraft: Aircraft) -> None:
        if not aircraft.is_available():
            raise ValueError("The aircraft has a pending check.")
        if self._booked_seats() > aircraft._seat_capacity:
            raise ValueError("The aircraft has too few seats for the current bookings.")
        self._aircraft = aircraft

    def _booked_seats(self) -> int:
        return sum(not ticket._cancelled for ticket in self._tickets)

    def _ready_for_boarding(self) -> bool:
        return (
            self._gate is not None
            and self._gate._status == "Open"
            and self._aircraft is not None
            and self._aircraft.is_available()
        )

    def summary(self) -> str:
        gate = self._gate._gate_code if self._gate is not None else "Unassigned"
        return (
            f"Flight {self._flight_number} | {self._origin._iata_code} to "
            f"{self._destination._iata_code} | Gate {gate} | {self._status}"
        )


class Passenger:
    def __init__(self, passenger_id: str, full_name: str, passport_no: str):
        self._passenger_id = passenger_id
        self._full_name = full_name
        self._passport_no = passport_no
        self._tickets: list[Ticket] = []
        self._claims: list[BaggageClaim] = []

    def book(self, flight: Flight, fare: Decimal) -> Ticket:
        if flight._status not in {"Scheduled", "Delayed"}:
            raise ValueError("Bookings are closed for this flight.")
        aircraft = flight._aircraft
        if aircraft is not None and flight._booked_seats() >= aircraft._seat_capacity:
            raise ValueError("This flight is full.")

        number = f"{self._passenger_id}-T{len(self._tickets) + 1}"
        ticket = Ticket(number, fare, self, flight)
        self._tickets.append(ticket)
        flight._tickets.append(ticket)
        return ticket

    def file_claim(self, tag: str) -> BaggageClaim:
        bag = self._find_bag(tag.strip())
        if bag is None:
            raise ValueError("Use a tag from your own checked baggage.")

        claim_id = f"{self._passenger_id}-C{len(self._claims) + 1}"
        claim = BaggageClaim(claim_id, self, bag)
        destination = bag._ticket._flight._destination
        destination._claims[claim_id] = claim
        self._claims.append(claim)
        return claim

    def _find_bag(self, tag: str) -> Baggage | None:
        for ticket in self._tickets:
            for bag in ticket._baggage:
                if bag._tag_number == tag:
                    return bag
        return None


class Ticket:
    def __init__(self, ticket_number: str, fare: Decimal, passenger: Passenger, flight: Flight):
        if not fare.is_finite() or fare < 0:
            raise ValueError("Enter a valid fare of zero or more.")
        self._ticket_number = ticket_number
        self._issued_on = date.today()
        self._fare = fare
        self._passenger = passenger
        self._flight = flight
        self._cancelled = False
        self._boarding_pass: BoardingPass | None = None
        self._baggage: list[Baggage] = []

    def issue_pass(self, seat_number: str, boarding_at: datetime) -> BoardingPass:
        if self._cancelled or self._flight._status in {"Cancelled", "Departed"}:
            raise ValueError("A boarding pass requires an active ticket and flight.")
        seat = seat_number.strip().upper()
        if not seat or boarding_at > self._flight._departure_at:
            raise ValueError("Enter a seat and a boarding time by departure.")
        current_pass = self._boarding_pass
        if current_pass is not None:
            if seat == current_pass._seat_number and boarding_at == current_pass._boarding_at:
                return current_pass
            raise ValueError("This ticket already has a boarding pass.")

        for ticket in self._flight._tickets:
            existing_pass = ticket._boarding_pass
            if (
                not ticket._cancelled
                and existing_pass is not None
                and existing_pass._seat_number == seat
            ):
                raise ValueError(f"Seat {seat} is already assigned on this flight.")

        self._boarding_pass = BoardingPass(f"BP-{self._ticket_number}", seat, boarding_at, self)
        return self._boarding_pass

    def cancel(self) -> None:
        if self._boarding_pass is not None and self._boarding_pass._boarded:
            raise ValueError("This passenger has already boarded.")
        self._cancelled = True

    def check_bag(self, tag_number: str, weight_kg: Decimal) -> Baggage:
        if self._cancelled or self._flight._status in {"Cancelled", "Departed"}:
            raise ValueError("Baggage check-in requires an active ticket and flight.")
        tag = tag_number.strip()
        if not tag or self._passenger._find_bag(tag) is not None:
            raise ValueError("Enter a new baggage tag.")
        bag = Baggage(tag, weight_kg, self)
        bag.check_in()
        self._baggage.append(bag)
        return bag


class BoardingPass:
    def __init__(self, pass_id: str, seat_number: str, boarding_at: datetime, ticket: Ticket):
        self._pass_id = pass_id
        self._seat_number = seat_number
        self._boarding_at = boarding_at
        self._ticket = ticket
        self._boarded = False

    @property
    def pass_id(self) -> str:
        return self._pass_id

    @property
    def boarded(self) -> bool:
        return self._boarded

    def scan(self) -> bool:
        flight = self._ticket._flight
        return (
            not self._boarded
            and not self._ticket._cancelled
            and flight._status == "Boarding"
            and flight._ready_for_boarding()
        )

    def mark_boarded(self) -> None:
        if not self.scan():
            raise ValueError("The boarding pass is unavailable for boarding.")
        self._boarded = True


class Baggage:
    def __init__(self, tag_number: str, weight_kg: Decimal, ticket: Ticket):
        if not weight_kg.is_finite() or weight_kg <= 0:
            raise ValueError("Baggage weight must be positive.")
        self._tag_number = tag_number
        self._weight_kg = weight_kg
        self._status = "Pending"
        self._ticket = ticket

    @property
    def status(self) -> str:
        return self._status

    def check_in(self) -> None:
        if self._status == "Delivered":
            raise ValueError("This bag has already been delivered.")
        self._status = "Checked in"

    def mark_delivered(self) -> None:
        if self._status == "Pending":
            raise ValueError("Check in the bag before marking it as delivered.")
        self._status = "Delivered"


class BaggageClaim:
    def __init__(self, claim_id: str, passenger: Passenger, bag: Baggage):
        self._claim_id = claim_id
        self._filed_on = date.today()
        self._status = "Filed"
        self._passenger = passenger
        self._bag = bag
        self._handled_by: Staff | None = None

    @property
    def claim_id(self) -> str:
        return self._claim_id

    @property
    def status(self) -> str:
        return self._status

    def mark_in_review(self) -> None:
        if self._status == "Resolved":
            raise ValueError("This baggage claim has already been resolved.")
        self._status = "In review"

    def resolve(self) -> None:
        if self._status == "Filed":
            raise ValueError("Review the baggage claim before resolving it.")
        self._status = "Resolved"


class Staff:
    def __init__(self, staff_id: str, full_name: str, role: str, airport: Airport):
        self._staff_id = staff_id
        self._full_name = full_name
        self._role = role
        self._airport = airport

    def verify_pass(self, pass_id: str) -> bool:
        for flight in self._airport._departures:
            for ticket in flight._tickets:
                boarding_pass = ticket._boarding_pass
                if boarding_pass is not None and boarding_pass.pass_id == pass_id:
                    return boarding_pass.scan()
        return False

    def review_claim(self, claim_id: str) -> None:
        claim = self._airport._claims.get(claim_id)
        if claim is None:
            raise ValueError("No baggage claim with that ID is filed at this airport.")
        claim.mark_in_review()
        claim._handled_by = self


def main() -> None:
    """Run a sample booking, boarding, and baggage claim."""
    origin = Airport("RUH", "Example Riyadh Airport", "Riyadh", "A12", "1")
    destination = Airport("JED", "Example Jeddah Airport", "Jeddah", "B5", "1")
    flight = Flight("EX101", datetime(2026, 11, 22, 14), origin, destination)
    origin.plan_flight(flight)
    gate = origin.assign_gate(flight, "A12")
    flight.assign_aircraft(Aircraft("EX-001", "Example aircraft", 180))

    passenger = Passenger("P001", "Omar Hassan", "SAMPLE001")
    ticket = passenger.book(flight, Decimal("320.00"))
    bag = ticket.check_bag("TAG001", Decimal("16.5"))
    boarding_pass = ticket.issue_pass("12A", datetime(2026, 11, 22, 13, 30))

    gate.open()
    flight.open_boarding()
    gate_agent = Staff("S001", "Nora Ali", "Gate agent", origin)
    pass_verified = gate_agent.verify_pass(boarding_pass.pass_id)
    if pass_verified:
        boarding_pass.mark_boarded()

    print("AIRPORT MANAGEMENT SYSTEM")
    print(flight.summary())
    print(f"Boarding pass verified: {pass_verified}")
    print(f"Passenger boarded: {boarding_pass.boarded}")
    print(f"Baggage status at departure: {bag.status}")

    flight.set_status("Departed")
    gate.close()
    claim = passenger.file_claim("TAG001")
    baggage_agent = Staff("S002", "Salma Ahmed", "Baggage agent", destination)
    baggage_agent.review_claim(claim.claim_id)
    print(f"Baggage claim {claim.claim_id}: {claim.status}")

    bag.mark_delivered()
    claim.resolve()
    print(f"Baggage status after recovery: {bag.status}")
    print(f"Final claim status: {claim.status}")


if __name__ == "__main__":
    main()
