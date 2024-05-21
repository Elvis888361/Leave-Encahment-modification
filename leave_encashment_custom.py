import datetime
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, nowdate

from erpnext.hr.doctype.leave_allocation.leave_allocation import get_unused_leaves
from erpnext.hr.doctype.leave_ledger_entry.leave_ledger_entry import create_leave_ledger_entry
from erpnext.hr.utils import set_employee_name, validate_active_employee
from erpnext.payroll.doctype.salary_structure_assignment.salary_structure_assignment import (
	get_assigned_salary_structure,
)

from erpnext.hr.doctype.leave_encashment.leave_encashment import (
    LeaveEncashment
)

def validate(self):
    set_employee_name(self)
    validate_active_employee(self.employee)
    self.get_leave_details_for_encashment()
    self.validate_salary_structure()

    if not self.encashment_date:
        self.encashment_date = getdate(nowdate())
@frappe.whitelist()
def get_leave_details_for_encashment(self):
    salary_structure = get_assigned_salary_structure(self.employee, self.encashment_date or getdate(nowdate()))
    if not salary_structure:
        frappe.throw(_("No Salary Structure assigned for Employee {0} on given date {1}").format(self.employee, self.encashment_date))

    if not frappe.db.get_value("Leave Type", self.leave_type, 'allow_encashment'):
        frappe.throw(_("Leave Type {0} is not encashable").format(self.leave_type))

    allocation = self.get_leave_allocation()

    if not allocation:
        frappe.throw(_("No Leaves Allocated to Employee: {0} for Leave Type: {1}").format(self.employee, self.leave_type))

    self.leave_balance = allocation.total_leaves_allocated - allocation.carry_forwarded_leaves_count\
        - get_unused_leaves(self.employee, self.leave_type, allocation.from_date, self.encashment_date)

    encashable_days = self.leave_balance - frappe.db.get_value('Leave Type', self.leave_type, 'encashment_threshold_days')
    self.encashable_days = encashable_days if encashable_days > 0 else 0
    this_doc = frappe.get_single("HR Settings")
    if hasattr(this_doc, 'disable_overall_pay_per_day'):
        if this_doc.disable_overall_pay_per_day is None:
            frappe.throw("Field disable_overall_pay_per_day does not exist on HR Settings")
        else:
            if this_doc.disable_overall_pay_per_day == 1:
                base = get_assigned_salary_structure_assignment_base(self.employee, self.encashment_date or getdate(nowdate()))
                if not base:
                    frappe.throw(_("No Salary Structure assignment for Employee {0} on given date {1}").format(self.employee, self.encashment_date))
                salary_structure_assignment_base=float(base)/float(self.days_taken_default)
                self.encashment_amount = self.encashable_days * salary_structure_assignment_base if salary_structure_assignment_base > 0 else 0

                self.leave_allocation = allocation.name
                return True
            else:
                per_day_encashment = frappe.db.get_value('Salary Structure', salary_structure , 'leave_encashment_amount_per_day')
                self.encashment_amount = self.encashable_days * per_day_encashment if per_day_encashment > 0 else 0

                self.leave_allocation = allocation.name
                return True
    else:
        per_day_encashment = frappe.db.get_value('Salary Structure', salary_structure , 'leave_encashment_amount_per_day')
        self.encashment_amount = self.encashable_days * per_day_encashment if per_day_encashment > 0 else 0

        self.leave_allocation = allocation.name
        return True
def get_assigned_salary_structure_assignment_base(employee, on_date):
    if not employee or not on_date:
        return None
    
    # Ensure on_date is correctly formatted
    if isinstance(on_date, datetime.date):
        on_date = on_date.strftime('%Y-%m-%d')
    
    # Debug: Print the parameters
    print(f"employee: {employee}, on_date: {on_date}")
    
    base = frappe.db.sql("""
        select base from `tabSalary Structure Assignment`
        where employee=%(employee)s
        and docstatus = 1
        and %(on_date)s >= from_date order by from_date desc limit 1""", {
            'employee': employee,
            'on_date': on_date,
        })
    
    # Debug: Print the SQL query result
    print(f"SQL Result: {base}")
    
    return base[0][0] if base else None


LeaveEncashment.validate=validate
LeaveEncashment.get_leave_details_for_encashment=get_leave_details_for_encashment