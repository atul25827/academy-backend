# Academy App Backend Schema

This document details the schema for the **Academy** Frappe application. It includes definitions for all DocTypes, their fields, types, and relationships.

## Table of Contents
- [Academy App Backend Schema](#academy-app-backend-schema)
  - [Table of Contents](#table-of-contents)
  - [Masters](#masters)
    - [Academy Master](#academy-master)
    - [Company Master](#company-master)
    - [Department Master](#department-master)
    - [Hall Master](#hall-master)
    - [IT Requirement](#it-requirement)
  - [Transactions](#transactions)
    - [Booking](#booking)
  - [Child Tables](#child-tables)
    - [Approver Child](#approver-child)
    - [Attachment](#attachment)
    - [Event Planning Child](#event-planning-child)

---

## Masters

### Academy Master
*Stores information about different academies.*

| Field Label      | Field Name     | Type   | Options / Link | Mandatory | Unique |
| :--------------- | :------------- | :----- | :------------- | :-------: | :----: |
| **Academy Name** | `academy_name` | Data   | -              |     ✅     |   ✅    |
| **Attachment**   | `attachment`   | Attach | -              |     -     |   -    |

### Company Master
*Stores corporate verticals or companies.*

| Field Label      | Field Name     | Type | Options / Link | Mandatory | Unique |
| :--------------- | :------------- | :--- | :------------- | :-------: | :----: |
| **Company Name** | `company_name` | Data | -              |     -     |   ✅    |

### Department Master
*Stores department definitions.*

| Field Label         | Field Name        | Type | Options / Link | Mandatory | Unique |
| :------------------ | :---------------- | :--- | :------------- | :-------: | :----: |
| **Department Name** | `department_name` | Data | -              |     -     |   ✅    |

### Hall Master
*Stores information about halls within an academy.*

| Field Label       | Field Name      | Type  | Options / Link                    | Mandatory | Unique |
| :---------------- | :-------------- | :---- | :-------------------------------- | :-------: | :----: |
| **Hall Name**     | `hall_name`     | Data  | -                                 |     -     |   -    |
| **Academy Name**  | `academy_name`  | Link  | [Academy Master](#academy-master) |     -     |   -    |
| **Capacity**      | `capacity`      | Int   | -                                 |     -     |   -    |
| **Wifi**          | `wifi`          | Check | -                                 |     -     |   -    |
| **Screen**        | `screen`        | Check | -                                 |     -     |   -    |
| **Remote Screen** | `remote_screen` | Check | -                                 |     -     |   -    |
| **Attachment**    | `attachment`    | Table | [Attachment](#attachment)         |     -     |   -    |

### IT Requirement
*Stores standard IT requirements for events.*

| Field Label     | Field Name    | Type | Options / Link | Mandatory | Unique |
| :-------------- | :------------ | :--- | :------------- | :-------: | :----: |
| **Requirement** | `requirement` | Data | -              |     -     |   -    |

---

## Transactions

### Booking
*The central document for managing event bookings.*

| Field Label              | Field Name                                                                         | Type       | Options / Link                                                         | Mandatory | Unique |
| :----------------------- | :--------------------------------------------------------------------------------- | :--------- | :--------------------------------------------------------------------- | :-------: | :----: |
| **Booking Id**           | `booking_id`                                                                       | Data       | -                                                                      |     ✅     |   ✅    |
| **Academy**              | [academy](file://wsl.localhost/Ubuntu2.0/home/atulchune/frappe-bench/apps/academy) | Link       | [Academy Master](#academy-master)                                      |     -     |   -    |
| **Merilian Code**        | `merilian_code`                                                                    | Data       | -                                                                      |     -     |   -    |
| **Full Name**            | `full_name`                                                                        | Data       | -                                                                      |     -     |   -    |
| **Email**                | `email`                                                                            | Data       | -                                                                      |     -     |   -    |
| **Contact Number**       | `contact_number`                                                                   | Data       | -                                                                      |     -     |   -    |
| **Vertical**             | `vertical`                                                                         | Link       | [Company Master](#company-master)                                      |     -     |   -    |
| **Department**           | `department`                                                                       | Data       | -                                                                      |     -     |   -    |
| **Event Title**          | `event_title`                                                                      | Data       | -                                                                      |     -     |   -    |
| **Description**          | `description`                                                                      | Small Text | -                                                                      |     -     |   -    |
| **Event Start Date**     | `event_start_date`                                                                 | Date       | -                                                                      |     -     |   -    |
| **Event End Date**       | `event_end_date`                                                                   | Date       | -                                                                      |     -     |   -    |
| **No of Participants**   | `no_of_participants`                                                               | Int        | -                                                                      |     -     |   -    |
| **IT Requirement**       | `it_requirement`                                                                   | Data       | -                                                                      |     -     |   -    |
| **Specific Requirement** | `speific_requirement_if_any`                                                       | Small Text | -                                                                      |     -     |   -    |
| **Mats Event**           | `mats_event`                                                                       | Select     | Yes, No                                                                |     -     |   -    |
| **Mats Request Number**  | `mats_request_number`                                                              | Data       | -                                                                      |     -     |   -    |
| **Event Status**         | `event_status`                                                                     | Select     | Submitted, Pending, Awaiting, Approved, Rejected, Attendence Submitted |     -     |   -    |
| **Overall Status**       | `overall_status`                                                                   | Data       | -                                                                      |     -     |   -    |
| **Is Submitted**         | `is_submitted`                                                                     | Check      | -                                                                      |     -     |   -    |
| **Is Rejected**          | `is_rejected`                                                                      | Check      | -                                                                      |     -     |   -    |
| **Is Approved**          | `is_approved`                                                                      | Check      | -                                                                      |     -     |   -    |
| **Attendence Submitted** | `attendence_submitted`                                                             | Check      | -                                                                      |     -     |   -    |
| **Event Planning**       | `event_planning`                                                                   | Table      | [Event Planning Child](#event-planning-child)                          |     -     |   -    |
| **Approver**             | `approver`                                                                         | Table      | [Approver Child](#approver-child)                                      |     -     |   -    |
| **Attachment**           | `table_trig`                                                                       | Table      | [Attachment](#attachment)                                              |     -     |   -    |

---

## Child Tables

### Approver Child
*Used in Booking to track approval steps.*

| Field Label         | Field Name        | Type   | Options / Link |
| :------------------ | :---------------- | :----- | :------------- |
| **Approver Name**   | `approver_name`   | Data   | -              |
| **Approver Status** | `approver_status` | Select | -              |
| **Remark**          | `remark`          | Data   | -              |

### Attachment
*Generic attachment child table.*

| Field Label    | Field Name   | Type   | Options / Link |
| :------------- | :----------- | :----- | :------------- |
| **File**       | `file`       | Attach | -              |
| **Is Deleted** | `is_deleted` | Check  | -              |

### Event Planning Child
*Details specific sessions/slots within a Booking.*

| Field Label          | Field Name         | Type | Options / Link              |
| :------------------- | :----------------- | :--- | :-------------------------- |
| **Hall**             | `hall`             | Link | [Hall Master](#hall-master) |
| **Booking Type**     | `booking_type`     | Link | [Booking](#booking)         |
| **Event Date**       | `event_date`       | Date | -                           |
| **Event Start Time** | `event_start_time` | Time | -                           |
| **Event End Time**   | `event_end_time`   | Time | -                           |
