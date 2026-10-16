# Code Review Findings

## 1. Task updates lack authorization checks

- **File:** `backend/projects/views.py`
- **Class and method:** `TaskDetailView.patch` (lines 165–185)
- **Category:** Security
- **Severity:** Critical
- **Impact:** The method loads and updates a task without checking that the requester belongs to its project or has an editing role. An authenticated viewer or non-member can change task fields, including status and assignee, by submitting a task ID.

## 2. Search query is interpolated into raw SQL

- **File:** `backend/projects/views.py`
- **Class and method:** `TaskListCreateView.get` (lines 110–123)
- **Category:** Security
- **Severity:** Critical
- **Impact:** The project ID and search query are inserted directly into SQL with f-strings. A crafted query can alter the SQL predicate and potentially return tasks from other projects, exposing their data to a project member.

## 3. Project name input is not validated on update

- **File:** `backend/projects/views.py`
- **Class and method:** `ProjectDetailView.patch` (lines 83–87)
- **Category:** Data Integrity
- **Severity:** High
- **Impact:** The update accepts a blank name and does not enforce the 120-character limit defined by the model. This can store invalid project names or cause a database error and HTTP 500 for an overlong name.

## 4. Changing task status can leave duplicate positions

- **File:** `backend/projects/views.py`
- **Class and method:** `TaskDetailView.patch` (lines 175–182); `ProjectDetailView.get` serializes tasks without explicit position ordering
- **Category:** Data Integrity
- **Severity:** Medium
- **Impact:** A status change keeps the task's old position instead of assigning a position in the destination column. Multiple tasks can therefore have the same position within a status, and project detail does not order the serialized tasks by position, so their displayed ordering can be inconsistent.
