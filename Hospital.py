"""Smart Hospital Management System based on the hospital UML diagram."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal


class Patient:
    def __init__(self, patient_id: str, full_name: str, date_of_birth: date):
        self._patient_id = patient_id
        self._full_name = full_name
        self._date_of_birth = date_of_birth
        self._room: HospitalRoom | None = None
        self._record = MedicalRecord(f"MR-{patient_id}")

    @property
    def full_name(self) -> str:
        return self._full_name

    def update_name(self, name: str) -> None:
        if not name.strip():
            raise ValueError("The patient's name cannot be empty.")
        self._full_name = name.strip()

    def record(self) -> MedicalRecord:
        return self._record


class Doctor:
    def __init__(self, doctor_id: str, full_name: str, specialty: str):
        self._doctor_id = doctor_id
        self._full_name = full_name
        self._specialty = specialty

    @property
    def full_name(self) -> str:
        return self._full_name

    def prescribe(
        self,
        patient: Patient,
        prescription_id: str,
        instructions: str,
        medicine: Medicine,
    ) -> Prescription:
        return Prescription(prescription_id, instructions, medicine, self, patient.record())

    def order_test(self, patient: Patient, test_id: str, test_name: str) -> LabTest:
        return LabTest(test_id, test_name, self, patient.record())


class Appointment:
    def __init__(
        self,
        appointment_id: str,
        scheduled_at: datetime,
        patient: Patient,
        doctor: Doctor,
    ):
        self._appointment_id = appointment_id
        self._scheduled_at = scheduled_at
        self._status = "Scheduled"
        self._patient = patient
        self._doctor = doctor

    def reschedule(self, at: datetime) -> None:
        if self._status == "Cancelled":
            raise ValueError("Create a new appointment for a cancelled booking.")
        self._scheduled_at = at

    def cancel(self) -> None:
        self._status = "Cancelled"

    def summary(self) -> str:
        return (
            f"Appointment {self._appointment_id} | {self._patient.full_name} with "
            f"{self._doctor.full_name} | {self._scheduled_at:%Y-%m-%d %H:%M} "
            f"| {self._status}"
        )


class HospitalRoom:
    def __init__(self, room_number: str, room_type: str, capacity: int):
        if capacity < 1:
            raise ValueError("The room must have at least one bed.")
        self._room_number = room_number
        self._room_type = room_type
        self._capacity = capacity
        self._patients: list[Patient] = []

    def get_occupancy(self) -> int:
        return len(self._patients)

    def has_space(self) -> bool:
        return self.get_occupancy() < self._capacity

    def admit(self, patient: Patient) -> None:
        if patient._room is self:
            return
        if not self.has_space():
            raise ValueError(f"Room {self._room_number} is full.")
        if patient._room is not None:
            patient._room.discharge(patient)
        self._patients.append(patient)
        patient._room = self

    def discharge(self, patient: Patient) -> None:
        if patient._room is self:
            self._patients.remove(patient)
            patient._room = None


class Treatment:
    def __init__(
        self,
        treatment_id: str,
        description: str,
        started_on: date,
        record: MedicalRecord,
    ):
        self._treatment_id = treatment_id
        self._description = description
        self._started_on = started_on
        self._outcome: str | None = None
        self._status = "In progress"
        self._record = record
        self._bill: Bill | None = None
        record.log_care(self)

    @property
    def status(self) -> str:
        return self._status

    def set_outcome(self, text: str) -> None:
        self._outcome = text
        self._record._touch()

    def complete(self) -> None:
        self._status = "Completed"
        self._record._touch()


class Medicine:
    def __init__(self, medicine_id: str, name: str, stock_qty: int):
        if stock_qty < 0:
            raise ValueError("Stock cannot be negative.")
        self._medicine_id = medicine_id
        self._name = name
        self._stock_qty = stock_qty

    @property
    def name(self) -> str:
        return self._name

    def check_stock(self) -> int:
        return self._stock_qty

    def restock(self, qty: int) -> None:
        if qty < 1:
            raise ValueError("Enter a positive restock quantity.")
        self._stock_qty += qty


class Prescription:
    def __init__(
        self,
        prescription_id: str,
        instructions: str,
        medicine: Medicine,
        doctor: Doctor,
        record: MedicalRecord,
    ):
        self._prescription_id = prescription_id
        self._issued_on = date.today()
        self._instructions = instructions
        self._doctor = doctor
        self._record = record

        self._medicines = [medicine]
        record._add_prescription(self)

    def add_drug(self, item: Medicine) -> None:
        if item not in self._medicines:
            self._medicines.append(item)
            self._record._touch()

    def print_copy(self) -> None:
        names = ", ".join(medicine.name for medicine in self._medicines)
        print(f"Prescription {self._prescription_id} by {self._doctor.full_name}")
        print(f"  Medicines: {names}")
        print(f"  Instructions: {self._instructions}")


class Bill:
    def __init__(self, bill_id: str, total_amount: Decimal, patient: Patient):
        if not total_amount.is_finite() or total_amount < 0:
            raise ValueError("Enter a valid bill total of zero or more.")
        self._bill_id = bill_id
        self._total_amount = total_amount
        self._amount_paid = Decimal("0.00")
        self._patient = patient
        self._treatments: list[Treatment] = []

    def get_balance(self) -> Decimal:
        return self._total_amount - self._amount_paid

    def pay(self, amount: Decimal) -> None:
        if not amount.is_finite() or amount <= 0 or amount > self.get_balance():
            raise ValueError("Enter a positive payment up to the outstanding balance.")
        self._amount_paid += amount

    def add_treatment(self, item: Treatment) -> None:
        if item._record is not self._patient.record():
            raise ValueError("The treatment must belong to the patient on this bill.")
        if item._bill is self:
            return
        if item._bill is not None:
            raise ValueError("This treatment is already linked to another bill.")
        self._treatments.append(item)
        item._bill = self


class LabTest:
    def __init__(self, test_id: str, test_name: str, doctor: Doctor, record: MedicalRecord):
        self._test_id = test_id
        self._test_name = test_name
        self._result: str | None = None
        self._doctor = doctor
        self._record = record
        record.add_test(self)

    def record_result(self, value: str) -> None:
        if not value.strip():
            raise ValueError("Enter a test result.")
        self._result = value.strip()
        self._record._touch()

    def is_complete(self) -> bool:
        return self._result is not None


class MedicalRecord:
    def __init__(self, record_id: str):
        self._record_id = record_id
        self._updated_at = datetime.now()
        self._created_on = self._updated_at.date()
        self._treatments: list[Treatment] = []
        self._tests: list[LabTest] = []
        self._prescriptions: list[Prescription] = []

    def log_care(self, item: Treatment) -> None:
        if item._record is not self:
            raise ValueError("The treatment belongs to another medical record.")
        if item not in self._treatments:
            self._treatments.append(item)
            self._touch()

    def add_test(self, test: LabTest) -> None:
        if test._record is not self:
            raise ValueError("The lab test belongs to another medical record.")
        if test not in self._tests:
            self._tests.append(test)
            self._touch()

    def _add_prescription(self, prescription: Prescription) -> None:
        self._prescriptions.append(prescription)
        self._touch()

    def _touch(self) -> None:
        self._updated_at = datetime.now()

    def summary(self) -> str:
        return (
            f"Medical record {self._record_id} | {len(self._treatments)} treatment(s), "
            f"{len(self._tests)} lab test(s), {len(self._prescriptions)} prescription(s)"
        )


def main() -> None:
    """Run an example with fictional hospital records."""
    patient = Patient("P001", "Mariam Saleh", date(2000, 6, 12))
    doctor = Doctor("D001", "Dr. Sami Ali", "General Medicine")
    appointment = Appointment("A001", datetime(2026, 11, 22, 10), patient, doctor)
    appointment.reschedule(datetime(2026, 11, 22, 11))

    room = HospitalRoom("205", "General", 2)
    room.admit(patient)

    record = patient.record()
    treatment = Treatment("TR001", "Follow-up visit", date(2026, 11, 22), record)
    treatment.set_outcome("Follow-up recorded in the sample record.")
    treatment.complete()

    test = doctor.order_test(patient, "LT001", "Example lab test")
    test.record_result("Sample result entered")

    medicine = Medicine("M001", "Example medicine", 20)
    medicine.restock(10)
    prescription = doctor.prescribe(patient, "RX001", "Demonstration entry", medicine)

    bill = Bill("B001", Decimal("450.00"), patient)
    bill.add_treatment(treatment)
    bill.pay(Decimal("200.00"))

    print("SMART HOSPITAL MANAGEMENT SYSTEM")
    print(appointment.summary())
    print(f"Room occupancy: {room.get_occupancy()} of 2 beds")
    print(f"Treatment status: {treatment.status}")
    print(f"Lab test complete: {test.is_complete()}")
    prescription.print_copy()
    print(f"Medicine units in stock: {medicine.check_stock()}")
    print(record.summary())
    print(f"Outstanding balance: SAR {bill.get_balance():.2f}")


if __name__ == "__main__":
    main()
