import cgi
from datetime import datetime
from functools import wraps
import logging
import re
import sqlite3
import subprocess
import sys

from flask import Flask, request, url_for, render_template, json, make_response, redirect
# Someties I want to use a template but not use the render_template function in 
# Flask because it does a redirect or something.  I just want to create some HTML on the backend
from jinja2 import Environment, FileSystemLoader
env = Environment(loader=FileSystemLoader('../templates'))

webapp = Flask(
    __name__,
    static_folder='../static', 
    template_folder="../templates"
)

db_conn = None


def load_db(path):
    if not re.match("[/~_-a-zA-Z0-9.]+", path):
        sys.exit("what kind of path is that?")
    subprocess.call("sqlite3 %s .dump > current_dump.out" % path, shell=True)
    print "done dumping db!"
    current_script = ""
    line_counter = 0
    # The dump can be really big.  Don't load it all into memory...
    with open("current_dump.out") as file:
        for line in file:
            line_counter += 1
            current_script += line
            if line_counter % 10000 == 0:
                if line.startswith("INSERT"):
                    print "executed %s so far" % line_counter
                    db_conn.executescript(current_script)
                    current_script = ""
    db_conn.executescript(current_script)

    #db_conn.executescript(dump_commands)


if sys.argv[1] == "memory":
    print "creating in memory connection"
    db_conn = sqlite3.connect(":memory:", check_same_thread=False)
    load_db(sys.argv[2])
elif sys.argv[1] == "disk":
    print "creating connection to disk"
    db_conn = sqlite3.connect(sys.argv[2], check_same_thread=False)
else:
    sys.exit("unknown db type argument")

db_conn.row_factory = sqlite3.Row
def query_to_dicts(query, params, all_as_string=False):
    dicts = []
    cursor = db_conn.cursor()
    query_results = cursor.execute(query, params)
    final_results = []
    counter = 0
    for row in query_results:
        counter += 1
        if counter > 1000:
            break
        clean_dict = {}
        for key in row.keys():
            if not isinstance(row[key], basestring):
                clean_dict[key] = str(row[key])
            else:
                clean_dict[key] = row[key]
        final_results.append(clean_dict)

    return final_results

def sort_schema(schema):
    """Gives back sorted columns given a schema string"""
    columns = schema.split(",")
    columns.sort()
    # Move the "create table" to the top after sorting alphabetically
    is_create_table= [c.startswith("CREATE") for c in columns]
    index_of_create_table = is_create_table.index(True)
    columns.insert(0, columns.pop(index_of_create_table))
    return columns

@webapp.route("/sqlite-server/command", methods=["GET"])
def exec_command():
    command = request.args["command"]
    command = re.sub("^\s*:\s+", "", command)
    splitup = re.split("\s+", command);
    results = ""

    param_1 = None
    param_2 = None
    param_3 = None
    if len(splitup) > 0:
        param_1 = splitup[0]
    if len(splitup) > 1:
        param_2 = splitup[1]
    if len(splitup) > 2:
        param_3 = splitup[2]

    if param_1 == "s":
        query = "SELECT sql FROM sqlite_master WHERE tbl_name LIKE ?";
        table_name_like = "%" + param_2 + "%"
        schema = query_to_dicts(query, (table_name_like,))[0]["sql"]
        columns = sort_schema(schema)
        if param_3:
            columns = filter(lambda x: re.search(param_3, x), columns)
        results = ",".join(columns)
        results = re.sub(",", ",<br/>", results)
    elif param_1 == "t":
        query = "SELECT distinct(tbl_name) FROM sqlite_master"
        query_results = query_to_dicts(query, ())
        table_names = [row["tbl_name"] for row in query_results]
        if param_2:
            table_names = filter(lambda x: re.search(param_2, x), table_names)
        results = ", ".join(table_names)
        results = re.sub(",", ",<br/>", results)
    return results


@webapp.route("/sqlite-server/query", methods=["GET"])
def query():
    results_template = env.get_template('results.html')
    results = []
    keys = []
    if "query" in request.args:
        results = query_to_dicts(request.args["query"], (), all_as_string=True)
        if len(results) > 0:
            keys = results[0].keys()
            keys.sort()
    return results_template.render(results=results, keys=keys)


@webapp.route("/sqlite-server/app", methods=["GET"])
def main_page():
    return render_template("main.html")


if __name__ == "__main__":
    webapp.config["DEBUG"] = True
    webapp.run("0.0.0.0", port=6132)
