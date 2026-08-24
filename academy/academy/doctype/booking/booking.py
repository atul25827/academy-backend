# Copyright (c) 2026, Meril and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class Booking(Document):
	def validate(self):
		self.set_event_dates()
		self.set_is_external()

	def set_event_dates(self):
		if self.get("event_planning"):
			dates = [row.event_date for row in self.get("event_planning") if row.event_date and not int(row.get("is_deleted") or 0)]
			if dates:
				self.event_start_date = min(dates)
				self.event_end_date = max(dates)
			else:
				self.event_start_date = None
				self.event_end_date = None
		else:
			self.event_start_date = None
			self.event_end_date = None

	def set_is_external(self):
		has_external = False
		if self.get("event_planning"):
			for row in self.get("event_planning"):
				if not int(row.get("is_deleted") or 0):
					if row.get("booking_type") and "External" in row.booking_type:
						has_external = True
						break
		self.is_external = 1 if has_external else 0
