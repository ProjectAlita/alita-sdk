# pylint: disable=C0103

""" 'Quick&dirty' quota support tools """

import os
import os.path

from . import log


def quota_check(params=None, enforce=True, tag="Quota", verbose=False):
    """ Check dir size, raise an exception """
    if not isinstance(params, dict):
        return {"ok": True}
    #
    target = params.get("target", None)
    if target is None or not os.path.isdir(target):
        return {"ok": True}
    #
    limit = params.get("limit", None)
    if limit is None or not isinstance(limit, int):
        return {"ok": True}
    #
    total_size = 0
    #
    for root, _, files in os.walk(target):
        for name in files:
            path = os.path.join(root, name)
            total_size += os.path.getsize(path)
    #
    if verbose:
        log.info(
            "[%s] Target size: %s => %s bytes (limit: %s, enforce: %s)",
            tag, target, total_size, limit, enforce,
        )
    #
    if enforce and total_size > limit:
        return {"ok": False, "limit": limit, "total_size": total_size}
    #
    return {"ok": True}


def sqlite_vacuum(params=None):
    """ Execute VACUUM on Sqlite3 DB file """
    if not isinstance(params, dict):
        return
    #
    target = params.get("target", None)
    if target is None or not os.path.isdir(target):
        return
    #
    db_file = os.path.join(target, "chroma.sqlite3")
    if not os.path.isfile(db_file):
        return
    #
    import sqlite3  # pylint: disable=C0415
    #
    try:
        db_connection = sqlite3.connect(db_file)
        db_cursor = db_connection.cursor()
        #
        db_cursor.execute("VACUUM")
        #
        db_connection.commit()
        db_connection.close()
    except:  # pylint: disable=W0702
        log.exception("Failed to VACUUM: %s", db_file)
