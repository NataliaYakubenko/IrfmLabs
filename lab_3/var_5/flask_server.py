import flask
import sqlite3

import db.sql_consts as sc


_OK = 200
_BAD_REQUEST = 400
_NOT_FOUND = 404


app = flask.Flask(__name__)


def _get_db():
    db = getattr(flask.g, "_db_connection", None)
    if db is None:
        db = flask.g._db_connection = sqlite3.connect(sc.DATABASE)
        db.row_factory = lambda c, r: {x[0]: r[i] for i, x in enumerate(c.description)}
    return db


def _query_db(query, args=(), select=True):
    db = _get_db().execute(query, args)
    if select:
        return db.fetchall()
    _get_db().commit()


def _exists(obj_id):
    return len(_query_db(f"select 1 from {sc.SQL_TABLE} where Id = ?", [obj_id])) == 1


def _response(method, oid, status):
    return flask.jsonify({"method": method, "Id": oid, "status": status})


def _extend_params(args):
    params = args.to_dict()
    for field in sc.SQL_COLUMNS:
        if field not in params:
            params[field] = None
    return params


def _placeholders(fields):
    return tuple((f":{field}" for field in fields))


_SURVEY_PREFIX = "/api/survey"


@app.route("/api/")
def api_index():
    return flask.render_template("index.html", api_prefix=_SURVEY_PREFIX)


@app.route(_SURVEY_PREFIX + "/", methods=["GET"])
def survey_index():
    list_objs = _query_db(f"select * from {sc.SQL_TABLE}")
    return flask.jsonify({"total": len(list_objs), "rows": list_objs})


@app.route(_SURVEY_PREFIX + "/<int:obj_id>", methods=["GET"])
def survey_show(obj_id):
    if not _exists(obj_id):
        flask.abort(_NOT_FOUND)
    return flask.jsonify(
        _query_db(f"select * from {sc.SQL_TABLE} where Id = ?", [obj_id])[0]
    )


@app.route(_SURVEY_PREFIX, methods=["POST"])
@app.route(_SURVEY_PREFIX + "/<int:obj_id>", methods=["POST"])
def survey_create(obj_id=None):
    args = _extend_params(flask.request.args)

    if obj_id is not None:
        args["Id"] = obj_id

    _query_db(
        f"""insert into {sc.SQL_TABLE}
            ({','.join(args.keys())})
        values
            ({','.join(_placeholders(args.keys()))})""",
        args,
        False
    )

    if obj_id is None:
        obj_id = _query_db(
            f"select Id from {sc.SQL_TABLE} where rowid = last_insert_rowid()"
        )[0]["Id"]

    return _response("create", obj_id, _OK)


@app.route(_SURVEY_PREFIX + "/<int:obj_id>", methods=["PUT"])
def survey_update(obj_id):
    if not _exists(obj_id):
        flask.abort(_NOT_FOUND)

    args = flask.request.args.to_dict()
    args["Id"] = obj_id

    _query_db(
        f"""update {sc.SQL_TABLE}
        set {','.join(map('='.join, zip(args.keys(), _placeholders(args.keys()))))}
        where Id = :Id""",
        args,
        False
    )
    return _response("update", obj_id, _OK)


@app.route(_SURVEY_PREFIX + "/<int:obj_id>", methods=["DELETE"])
def survey_destroy(obj_id):
    if not _exists(obj_id):
        flask.abort(_NOT_FOUND)
    _query_db(f"delete from {sc.SQL_TABLE} where Id = ?", [obj_id], False)
    return _response("delete", obj_id, _OK)


@app.route(_SURVEY_PREFIX + "/number/<string:gender>", methods=["GET"])
def survey_number_of_people(gender):
    if gender not in ("male", "female"):
        flask.abort(_BAD_REQUEST)
    return flask.jsonify(
        _query_db(f"select count(*) as count from {sc.SQL_TABLE} where Gender = ?", [gender])[0]
    )


@app.teardown_appcontext
def close_connection(exception):
    db = flask.g.pop("_db_connection", None)
    if db is not None:
        db.commit()
        db.close()
