from flask import Blueprint

# from flask import request, jsonify
from virtual_assistant.database.database import Database

database_bp = Blueprint("database", __name__, url_prefix="/database")


@database_bp.route("/test_sqlite", methods=["GET"])
def test_sqlite():
    # Call the test_sqlite method from the Database class
    return Database.get_instance().test_sqlite()


# Add more routes for CRUD operations, such as:
# @database_bp.route("/create", methods=["POST"])
# def create():
#     # Implement create logic here
#
# @database_bp.route("/read", methods=["GET"])
# def read():
#     # Implement read logic here
#
# @database_bp.route("/update", methods=["PUT"])
# def update():
#     # Implement update logic here
#
# @database_bp.route("/delete", methods=["DELETE"])
# def delete():
#     # Implement delete logic here
