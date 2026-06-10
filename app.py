# app.py
# A simple Flask REST API for CodeCraftHub
# - All CRUD operations for "courses"
# - Data stored in a JSON file named courses.json (auto-created if missing)
# - Endpoints:
#     POST  /api/courses          -> create a new course
#     GET   /api/courses          -> get all courses or a single course by ?id=
#     PUT   /api/courses          -> update a course (requires id and all fields)
#     DELETE /api/courses          -> delete a course by id (in JSON body)

from datetime import datetime
import json
import os
import logging

# Configure logging once, at the top of your app (before routes)
logging.basicConfig(
    level=logging.INFO,                # INFO or DEBUG depending on verbosity
    format="%(asctime)s [%(levelname)s] %(message)s"
)

logger = logging.getLogger(__name__)

from flask import Flask, jsonify, request

app = Flask(__name__)

# File where courses will be persisted
DATA_FILE = 'data/courses.json'
ALLOWED_STATUSES = {"Not Started", "In Progress", "Completed"}


# --- Helper utilities ---

def ensure_data_file():
    """
    Ensure the data file exists. If not, create it with an empty list.
    This satisfies the "auto-create" requirement.
    """
    if not os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'w') as f:
                json.dump([], f, indent=2)
        except Exception as e:
            # If file can't be created, we'll surface this later via API errors
            logger.debug(f"Error creating data file: {e}")


def load_courses():
    """
    Read and return the list of courses from the JSON file.
    If the file is missing or contains invalid JSON, return an empty list.
    """
    ensure_data_file()
    try:
        with open(DATA_FILE, 'r') as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            else:
                # If the JSON root is not a list, treat as corrupted
                return []
    except json.JSONDecodeError:
        # Corrupted JSON
        return []
    except Exception as e:
        # Any other IO error
        logger.debug(f"Error reading data file: {e}")
        return []


def save_courses(courses):
    """
    Persist the list of courses back to the JSON file.
    Returns True on success, False on failure.
    """
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump(courses, f, indent=2)
        return True
    except Exception as e:
        logger.debug(f"Error writing data file: {e}")
        return False


def next_id(courses):
    """
    Compute the next auto-incremented id. Starts from 1.
    """
    if not courses:
        return 1
    return max(course['id'] for course in courses) + 1


def find_course(courses, course_id):
    """
    Find and return a course by its id from the given list, or None if not found.
    """
    for c in courses:
        if c.get('id') == course_id:
            return c
    return None


def is_valid_date(iso_str):
    """
    Validate that a string is a date in YYYY-MM-DD format.
    """
    try:
        datetime.strptime(iso_str, "%Y-%m-%d")
        return True
    except Exception:
        return False


def status_is_valid(status):
    """
    Check if the status is one of the allowed values.
    """
    return status in ALLOWED_STATUSES


def validate_course_fields(payload, require_all=False, include_id=False):
    """
    Validate the course payload.

    - payload: dict from request JSON
    - require_all: if True, all fields must be present (name, description, target_date, status)
    - include_id: if True, expect an 'id' field and validate its presence/type
    Returns (is_valid: bool, message: str)
    """
    if not payload:
        return False, "Missing JSON payload"

    if include_id:
        if 'id' not in payload:
            return False, "Missing field: id"
        # id will be validated where used (as int)

    name = payload.get('name')
    description = payload.get('description')
    target_date = payload.get('target_date')
    status = payload.get('status')

    if require_all:
        # When updating/creating we require all core fields
        missing = []
        if not name:
            missing.append("name")
        if not description:
            missing.append("description")
        if not target_date:
            missing.append("target_date")
        if not status:
            missing.append("status")
        if missing:
            return False, f"Missing fields: {', '.join(missing)}"

    if name is not None and not isinstance(name, str):
        return False, "name must be a string"
    if description is not None and not isinstance(description, str):
        return False, "description must be a string"
    if target_date is not None and not is_valid_date(target_date):
        return False, "target_date must be in YYYY-MM-DD format"
    if status is not None and not status_is_valid(status):
        return False, "status must be one of: Not Started, In Progress, Completed"

    return True, ""


# --- API endpoints ---

@app.route('/api/courses', methods=['POST'])
def create_course():
    """
    Create a new course.
    Required fields in JSON body: name, description, target_date (YYYY-MM-DD), status
    Automatically assigns id and created_at timestamp.
    """
    payload = request.get_json(silent=True)
    ok, msg = validate_course_fields(payload, require_all=True)
    if not ok:
        return jsonify({"error": msg}), 400

    courses = load_courses()
    course_id = next_id(courses)
    new_course = {
        "id": course_id,
        "name": payload['name'],
        "description": payload['description'],
        "target_date": payload['target_date'],
        "status": payload['status'],
        "created_at": datetime.utcnow().isoformat() + "Z"
    }

    print('Yo ibo!')
    print(courses)

    courses.append(new_course)
    if not save_courses(courses):
        return jsonify({"error": "Failed to write data to storage"}), 500

    return jsonify(new_course), 201


@app.route('/api/courses', methods=['GET'])
def get_courses():
    """
    Get all courses, or a single course if ?id= is provided.
    - No id: return all courses
    - id=<int>: return the specific course or 404 if not found
    """
    courses = load_courses()
    id_param = request.args.get('id')
    if id_param is not None:
        try:
            cid = int(id_param)
        except ValueError:
            return jsonify({"error": "id must be an integer"}), 400

        course = find_course(courses, cid)
        if not course:
            return jsonify({"error": "Course not found"}), 404
        return jsonify(course), 200

    return jsonify(courses), 200

# Get a course by id
@app.route('/api/courses/<int:course_id>', methods=['GET'])
def get_course(course_id):
    courses = load_courses()
    course = find_course(courses, course_id)
    if not course:
        return jsonify({"error": "Course not found"}), 404
    return jsonify(course), 200

# Update a course by id
@app.route('/api/courses/<int:course_id>', methods=['PUT'])
def update_course(course_id):
    payload = request.get_json(silent=True)
    ok, msg = validate_course_fields(payload, require_all=True)
    if not ok:
        return jsonify({"error": msg}), 400

    courses = load_courses()
    course = find_course(courses, course_id)
    if not course:
        return jsonify({"error": "Course not found"}), 404

    course.update({
        "name": payload['name'],
        "description": payload['description'],
        "target_date": payload['target_date'],
        "status": payload['status']
    })

    if not save_courses(courses):
        return jsonify({"error": "Failed to write data to storage"}), 500

    return jsonify(course), 200

# Delete a course by id
@app.route('/api/courses/<int:course_id>', methods=['DELETE'])
def delete_course(course_id):
    courses = load_courses()
    course = find_course(courses, course_id)
    if not course:
        return jsonify({"error": "Course not found"}), 404

    courses.remove(course)
    if not save_courses(courses):
        return jsonify({"error": "Failed to write data to storage"}), 500

    return jsonify({"message": "Course deleted"}), 200

# --- Run the app ---

if __name__ == '__main__':
    # Ensure the data file exists before starting
    ensure_data_file()
    # Start the Flask development server
    app.run(debug=True, host='0.0.0.0', port=5000)