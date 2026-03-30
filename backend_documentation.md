# End-to-End Backend Documentation: Academy (Club Booking System)

Welcome to the backend documentation for the **Academy App**. This guide is designed to rapidly onboard new developers, helping them understand the Frappe Framework intricacies, the database schema, business logic, APIs, and the approval architecture in 1 day.

---

## 1. 📌 Project Overview
The "Academy" backend is a custom application built on the Frappe Framework designed to handle comprehensive club booking operations. 

**Business Domain:** Club & Facility Booking Management.
**Key Features:**
- **Booking Creation:** Complex form handling where a single request manages parent booking details alongside multiple nested child entities (stay, catering, and approvals).
- **Dynamic Syncing:** Cross-sync functionalities where Food & Catering requests marked for "stay" automatically populate Stay arrangements.
- **Approval Workflow:** A sequenced, multi-level matrix approval system. Submissions route dynamically to distinct managers who act in a cascading order.

---

## 2. ⚙️ Tech Stack
- **Framework:** Frappe Framework (Python/Node backend ecosystem)
- **Backend Language:** Python 3.10+
- **Database:** MariaDB (Standard requirement for Frappe)
- **Caching & Background Jobs:** Redis (Handles queued jobs, async functions, session caching)
- **Frontend Interaction:** RESTful APIs consumed natively by an external frontend (e.g., Next.js / React app)

---

## 3. 🏗️ Backend Architecture (Frappe Specific)
Frappe utilizes a metadata-driven architectural model. Instead of writing raw SQL or boilerplate migrations, components are generated automatically.

- **DocTypes:** The heart of Frappe. A DocType acts as both the Database Table definition and the Model Controller class. It bridges the schema with Python logic.
- **Request Lifecycle:**
  1. **Client** makes a GET/POST request.
  2. Request routes through Frappe and hits an **API method** (decorated with `@frappe.whitelist()`).
  3. The API method resolves **DocType** models using the ORM (`frappe.get_doc()`, `frappe.db.get_value()`).
  4. Changes apply to the **Database** via the Document Object lifecycle (`doc.save()`, `doc.insert()`).
  5. The **Response** is formulated via returned Python dictionaries and automatically serialized down to JSON.

---

## 4. 📁 Folder Structure (VERY IMPORTANT)
The physical layout of the backend lives inside your local `frappe-bench/apps/` directory. For our project:

```text
apps/
 ├── academy/
      ├── academy/
           ├── doctype/     # Database schemas & Model controllers
           ├── api/         # Custom endpoints (e.g., club_booking.py)
           ├── hooks.py     # Global app config, events, & background jobs
           ├── utils/       # Shared logic, utilities, formatting helpers
           ├── workflows/   # Native Frappe Workflow JSON files
```

- **`doctype/`**: Modifying fields inside the Frappe UI generates `.json` schema dumps here. Python logic handling core standard document events (`before_save`, `on_update`) lives in the accompanying `.py` class.
- **`api/`**: We rely heavily on this folder! Instead of using Frappe’s generic CRUD REST endpoints, our explicit transaction rules (like syncing child tables) are written here.
- **`hooks.py`**: The central registry. Any recurring jobs or global event interceptions are declared here.

---

## 5. 🗄️ DocType Schema Documentation (CORE SECTION)

### **DocType: Club Booking**
*Purpose:* The central parent tracking document that manages the entire lifecycle of a requested event or facility usage.

**Key Fields:**
- `club_booking_id` (Data): Auto-generated sequential ID (e.g., `CB-FY25-00001`).
- `event_name` (Data): Event title.
- `from_date` / `to_date` (Date/Datetime): The duration span.
- `booking_status` (Select): State flags like 'Draft', 'Submitted', 'Approved', 'Rejected', 'Cancel Request'.
- `approval_status` (Data): A dynamic string for UI visibility (e.g., "Awaiting Approval from John Doe").
- `is_submitted`, `is_approved`, `is_rejected`, `is_cancelled` (Check): Boolean states. *Why? Quick binary toggles make SQL COUNT/SUM performance incredibly fast.*

**Relationships (Child Tables):**
- `approver` -> Links to Approver List.
- `food_and_catering` -> Links to Food and Stay Child schemas.
- `stay` -> Links to Food and Stay Child schemas.

---

## 6. 🔗 Child Tables (Detailed)
Child tables are specific DocTypes marked with "Is Submittable/Is Child Table". They cannot exist without a Parent.

### **Club Approver List Child**
- **How Linked:** Embedded in `Club Booking` inside the `approver` field.
- **Fields:**
  - `approver_name` (Link -> User): The assigned system user.
  - `level` (Int): Their sequence step.
  - `approver_status` (Select): 'Pending' (waiting on previous people), 'Awaiting' (their turn), 'Approved', 'Rejected'.
  - `action_date` (Datetime) & `remark` (Data).

### **Food and Stay Child**
- **How Linked:** Used twice in the parent as `food_and_catering` and `stay`.
- **Fields:**
  - `distributor_or_guest_name` (Data): The individual receiving accommodations.
  - `meal_type` (Select), `total_no_of_guest` (Int).
  - `check_in_date` / `check_out_date` (Date).
  - `is_stay` / `both_stay_and_food` (Check): System flags to trigger auto-replication.

---

## 7. 🔌 API Documentation (VERY IMPORTANT)
APIs are defined in `academy.api.club_booking`. 

### `create_booking(**kwargs)`
- **Method:** POST
- **Description:** Bulk inserts booking details while protecting the state in "Draft". Safely parses and injects stringified JSON child arrays.
- **Response:** `{ "status": "success", "club_booking_id": "...", "name": "..." }`

### `submit_booking(**kwargs)`
- **Method:** POST
- **Description:** Finalizes edits and triggers `_apply_approval_matrix`. Changes state to 'Submitted' and instantiates sequential approver rows.

### `get_club_booking_details(club_booking_id)`
- **Method:** GET
- **Description:** Pulls the document completely. Parses permission variables on-the-fly, returning a `can_approve` boolean ensuring the current logged-in user can actually action the record.

### `update_club_booking_status(club_booking_id, action, remark)`
- **Method:** POST
- **Description:** The core action engine. Processes 'Approve' or 'Reject' cascades to the next step or finalizes the booking completely.

### `get_club_approver_stats()` / `get_user_club_booking_stats()`
- **Method:** GET
- **Description:** High-volume dashboard APIs operating purely on SQL queries mapping `is_approved`/`is_submitted` checks to avoid loading heavy objects into memory.

---

## 8. 🔐 Authentication & Authorization
- **Login mechanics:** Relies on standard Frappe Web Session management or Token-Based Auth (`Authorization: token <key>:<secret>`).
- **Role-Based Access (RBAC):** Users should hold "Academy User" or "Academy Admin" roles to execute transactions. 
- **DocType permissions:** Role profiles are linked via Frappe's builtin Role Permissions Manager.
- **Row-Level checks:** Custom python validation actively verifies whether `user == child_row.approver_name` before allowing approval actions.

---

## 9. 🔄 Business Logic & Flow (VERY IMPORTANT)
This flow defines how the system progresses.

**Step-by-Step Flow:**
1. **User drafts request** ➔ Calls `create_booking`. The system applies logic via `_sync_stay_from_food()` (copies marked guests from catering directly into the stay block).
2. **User submits request** ➔ Calls `submit_booking`. Calls `_apply_approval_matrix()` directly updating states. Parent status is marked `is_submitted=1`.
3. **Approver logs in** ➔ Calls `get_club_booking_details`. The backend evaluates if their assigned row currently reads 'Awaiting'. If true, UI allows action.
4. **Approval Action** ➔ Calls `update_club_booking_status("Approve")`. The backend increments `current_index` and flips the *next* sequence approver from 'Pending' to 'Awaiting'.
5. **Finalization** ➔ The last approver triggers final logic, flagging `is_approved=1`.

---

## 10. 🔁 Approval Workflow
- **Assignment source:** `Club Approver Matrix` configures roles per context. The engine extracts the matrix lists sequentially. 
- **Status Transitions:**
  - **Pending:** Blocked.
  - **Awaiting:** Ready to be approved.
  - **Approved/Rejected:** Locked state.

---

## 11. ⚙️ Hooks & Events
- **`hooks.py`**: A central space exposing app components. Used to inject Custom CSS/JS on the UI, export API schemas, and bind functions to Frappe hooks.
- **Event interception:** Usually, Frappe uses `on_submit`, `before_save`, `after_insert`. In **this architecture**, to keep frontend API guarantees strict, we execute logic directly in our custom Endpoints (e.g. executing `_sync_stay_from_food(doc)` manually before `.save()` instead of purely relying on `before_save` hooks).

---

## 12. 🔄 Background Jobs
- **Redis ecosystem:** Frappe relies heavily on Redis queues natively for async work. 
- **Possible use cases:** Sending notification emails upon an approval progression. Triggered using `frappe.enqueue("academy.api.emails.notify_approver", queue="short", booking_id=doc.name)`.

---

## 13. 📡 Data Flow (End-to-End)
**Scenario: Submitting a Booking**
1. **[UI] Frontend Form** constructs a complex JSON payload containing base fields and nested lists of Food/Stay definitions.
2. **[HTTP] POST Router** locates `/api/method/academy.api.club_booking.submit_booking`.
3. **[Python] API Execution:** 
   - `_parse_child_tables` decodes the payload grids.
   - `_sync_stay_from_food` normalizes dependencies.
   - `_apply_approval_matrix` generates routing rules in memory.
4. **[ORM] DB Save:** Calls `doc.insert()`. Frappe ORM safely casts models to DB inserts inside MariaDB.
5. **[Response] JSON** returns `{ status: "success", club_booking_id: "CB..."}` back to updating the UI state.

---

## 14. ⚙️ Setup & Installation
Steps required for new setup:
```bash
# 1. Initialize Bench (Framework Manager)
bench init frappe-bench
cd frappe-bench

# 2. Extract and link the app repository
bench get-app https://github.com/organization/academy.git

# 3. Create Frappe local database Site
bench new-site academy.local

# 4. Install the custom app logic onto the site
bench --site academy.local install-app academy

# 5. Start the underlying Redis, Workers, and Server
bench start
```
*Tip: Ensure your OS `hosts` file supports custom domains like `academy.local` correctly resolving to standard loopbacks.*

---

## 15. 🚀 Deployment
- **Production Paradigm:** Uses **NGINX** as the reverse HTTP proxy binding routes to an internal **Gunicorn** app server managed implicitly by **Supervisor**, which keeps workers online.
- **Commands:** 
  - `bench setup production [frappe-user]` configures NGINX/Supervisor auto-configs.
  - `bench migrate` rapidly modifies schema alters directly into the mapped MariaDB database instance without dropping rows.

---

## 16. ⚠️ Common Issues & Fixes
- **Static Pyre Typings Errors in Loops:** Because Frappe generates complex models at runtime, type analysis limits augmented variables inside loops (e.g. `total_approved += 1` throwing errors regarding `Literal[1]`). **Fix:** Break inferences via `int(total_approved) + 1`.
- **API Returning 500 / Frappe Exception Tracebacks:** 99% caused by the frontend transmitting standard nested objects; whereas custom APIs typically require Child Table representations serialized using `JSON.stringify()`.
- **AttributeError: module has no attribute X:** Endpoint typo mappings. Review `/api/club_booking.py` closely.

---

## 17. 🧠 Important Design Decisions
- **Why build monolithic APIs instead of standard Frappe REST CRUD?** Native Frappe APIs require a single transaction to save a Parent. You have to save Child rows separatedly. A monolithic API `create_booking` performs high-performance bulk-inserts, immediately verifying complex dependencies directly.
- **Checkbox Metadata:** Status logic leverages flags (`is_approved`, `is_submitted`). SQL querying a massive indexed boolean `WHERE is_approved = 1` takes mere milliseconds compared to searching nested Table JSONs.

---

## 18. 🔁 Extensibility Guide
- **How to add a new Field:** DO NOT edit the JSON directly. Log into Frappe Desk. Go to DocType list -> `Club Booking`. Add new fields. Click Save. The DB mapping automatically registers.
- **How to append new Business Logic API:** Create the method inside `api/club_booking.py`. Decorate it entirely with `@frappe.whitelist()`. 
- **Modify Workflows:** If parallel (rather than sequential) approvals are requested tomorrow, rewrite the isolated internal `_apply_approval_matrix()` module logic. It won't break upstream APIs.

---

## 19. 📌 Naming Conventions
- **DocTypes:** Capitalized Title Case (e.g. `Club Booking`).
- **Standard DB Fields:** Standard `snake_case` format (e.g. `event_name`, `booking_status`). Let this closely reflect their respective frontend API payload properties map to perfectly synchronize forms.
- **API Action Naming:** Leading verb constructs (e.g. `create_booking`, `get_club_booking_list`).

---


## 🔥 Quick Reference Cheat Sheet (DocTypes + APIs + Flows in 1 page)

**Key DocTypes**
| 🛠 Component | 📝 Name | 💡 Purpose |
|---------|------|---------|
| **Parent DocType** | `Club Booking` | Represents the core timeline event request. |
| **Schema Config**| `Club Approver Matrix`| Stores organization management hierarchies. |
| **Child DocType** | `Club Approver List Child`| Sequential step allocations for workflow. |
| **Child DocType** | `Food and Stay Child` | Identical schemas utilized in arrays for modular components. |

**Key APIs (`academy.api.club_booking.`)**
| 🔌 Name | 🌐 HTTP | ⚙️ Description |
|---|---|---|
| `create_booking` | POST | Mass injects arrays and syncs lists safely into 'Draft' mode. |
| `submit_booking` | POST | Transitions mode, building required cascading roles directly via Matrix. |
| `update_club_booking_status` | POST | Evaluates credentials & progresses routing cascade forward iteratively. |
| `get_club_booking_details` | GET | Comprehensive query pulling out array relationships entirely. |
| `get_club_approver_stats` | GET | Counter-aggregation optimization algorithm utilizing simple queries. |

**Key Flows**
- **Creation Flow:** Frontend Payload -> `create_booking` -> `_parse_child_tables()` -> `_sync_stay_from_food()` -> `doc.insert()` (Draft)
- **Approval Flow:** `submit_booking` -> Approver hits `update_club_booking_status("Approve")` -> Next Approver Row changes to 'Awaiting' -> Last Approver completes booking (`is_approved=1`).

---

## 🔍 Where to find what in code
- **APIs & Business Logic:** `apps/academy/academy/api/club_booking.py` (Functions: `create_booking`, `_sync_stay...`, `_apply_...`)
- **Frappe UI overrides (Class Controllers):** `apps/academy/academy/doctype/club_booking/club_booking.py`
- **Global App Context & Events:** `apps/academy/academy/hooks.py`
- **Schema Blueprint Files (Auto-generated):** `apps/academy/academy/doctype/*/*.json`
