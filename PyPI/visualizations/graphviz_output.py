#!/usr/bin/env python

"""
Generate a dotfile for Python module dependencies.
"""

import json
import logging
import sys
from typing import Dict, List
import sqlite3

import progressbar

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(message)s",
    level=logging.DEBUG,
    stream=sys.stdout,
)


def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d


def main(filename: str, n: int, remove_no_edge: bool, remove_only_selfimport: bool):
    """
    Fetch data from server and create the graphviz data.

    Parameters
    ----------
    filename : str
        The path where the doftile gets written to.
    n : int
        The number of nodes it may have. None for all nodes.
    remove_no_edge : bool
        Remove packages which are neither imported nor do import anything.
    remove_only_selfimport : bool
        Remove packages which only import themselves.
    """
    connection = sqlite3.connect("pypi.db")
    connection.row_factory = dict_factory
    cursor = connection.cursor()
    logging.info("Start fetching data from database...")
    sql = "SELECT `id`, `name` FROM `packages`"
    cursor.execute(sql)
    packages = cursor.fetchall()
    sql = "SELECT `package`, `needs_package`, `times` FROM `dependencies`"
    cursor.execute(sql)
    dependencies = cursor.fetchall()
    logging.info("Start writing graphviz file...")
    create_graphviz(
        filename, packages, dependencies, n, remove_no_edge, remove_only_selfimport
    )


def create_graphviz(
    filename: str,
    packages: List[Dict],
    dependencies: List[Dict],
    n: int,
    remove_no_edge: bool,
    remove_only_selfimport: bool,
):
    """
    Parameters
    ----------
    filename : str
        Path to the file where the GraphViz data will be stored.
    packages: list of dicts
        Each dict represents a package. It has the keys 'id' and 'name'
    dependencies : list of dicts
        Each dict has the keys 'package', 'needs_package' and 'times'
    n : int
        The number of nodes it may have. None for all nodes.
    remove_no_edge : bool
        Remove packages which are neither imported nor do import anything.
    remove_only_selfimport : bool
        Remove packages which only import themselves.
    """
    if remove_no_edge or remove_only_selfimport:
        save_nodes = set()
        for dep in dependencies:
            save_nodes.add(dep["needs_package"])
            save_nodes.add(dep["package"])
        new_pkgs = []
        logging.info(
            f"Imported graph had {len(packages)} nodes. "
            f"Only {len(save_nodes)} of them have edges."
        )
        for pkg in packages:
            if pkg["id"] in save_nodes:
                new_pkgs.append(pkg)
        packages = new_pkgs

    if remove_only_selfimport:
        # storea all dependencies, except self-dependencies
        has_dependency = {}
        for dep in dependencies:
            if dep["package"] == dep["needs_package"]:
                continue
            if dep["package"] in has_dependency:
                has_dependency[dep["package"]].append(dep["needs_package"])
            else:
                has_dependency[dep["package"]] = [dep["needs_package"]]
        new_pkgs = []
        logging.info("Remove packages which only import themselves.")
        for pkg in packages:
            if pkg["id"] in has_dependency and len(has_dependency[pkg["id"]]) >= 1:
                new_pkgs.append(pkg)
        packages = new_pkgs
    logging.info(f"{len(packages)} packages remaining")
    packages = packages[:n]

    with open(filename, "w") as f:
        # digraph is for "directed graph"
        f.write("digraph python_package_dependencies {\n")
        # f.write("rankdir=LR;\n")
        # f.write('size="8,5"\n')

        pkg_ids = []
        for pkg in progressbar.progressbar(packages[:n]):
            # Remove 'shape=point,' for Gephi
            f.write(f'{pkg["id"]} [shape=point, label="{pkg["name"]}"];\n')
            pkg_ids.append(pkg["id"])

        pkg_ids = set(pkg_ids)  # This is a EXTREME speedup!
        # f.write("\n")
        for dep in progressbar.progressbar(dependencies):
            if dep["needs_package"] in pkg_ids and dep["package"] in pkg_ids:
                f.write(f"{dep['needs_package']} -> {dep['package']};\n")
        f.write("}")


def get_parser():
    from argparse import ArgumentDefaultsHelpFormatter, ArgumentParser

    parser = ArgumentParser(
        description=__doc__, formatter_class=ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "-f",
        "--file",
        dest="filename",
        help="write doftile to FILE",
        default="graphviz.dot",
        metavar="FILE",
    )
    parser.add_argument(
        "-n", dest="n", type=int, help="how many nodes the graph will have"
    )
    parser.add_argument(
        "-r",
        "--remove",
        action="store_true",
        dest="remove_no_edge",
        default=False,
        help="remove packages which are not importet and " "do not import",
    )
    parser.add_argument(
        "-s",
        "--remove_selfimport_only",
        action="store_true",
        dest="remove_selfimport_only",
        default=False,
        help="remove packages which are not importet, do not "
        "import except for / by themselves",
    )
    return parser


if __name__ == "__main__":
    args = get_parser().parse_args()
    main(args.filename, args.n, args.remove_no_edge, args.remove_selfimport_only)
