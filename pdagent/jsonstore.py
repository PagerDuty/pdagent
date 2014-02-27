#
# Copyright (c) 2013-2014, PagerDuty, Inc. <info@pagerduty.com>
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#   * Redistributions of source code must retain the above copyright
#     notice, this list of conditions and the following disclaimer.
#   * Redistributions in binary form must reproduce the above copyright
#     notice, this list of conditions and the following disclaimer in the
#     documentation and/or other materials provided with the distribution.
#   * Neither the name of the copyright holder nor the
#     names of its contributors may be used to endorse or promote products
#     derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#


import json
import os


class JsonStore(object):
    """
    A file-based JSON store to persist JSON-based data atomically.
    """

    def __init__(self, db_name, db_dir):
        from pdagentutil import \
            ensure_readable_directory, ensure_writable_directory
        ensure_readable_directory(db_dir)
        ensure_writable_directory(db_dir)
        self._path = os.path.join(db_dir, db_name)
        self._backup_path = os.path.join(db_dir, "%s.bak" % db_name)

    def get(self):
        """
        Get existing data from the JSON in the db file.
        Returns None if it cannot load the data for any reason.
        This includes bad json, file does not exist or any other
        error reading the file.
        """
        fp = None
        try:
            fp = open(self._path, "r")
            return json.load(fp)
        except (IOError, ValueError):
            # file could not be opened, or had bad json in it.
            return None
        finally:
            if fp:
                fp.close()

    def set(self, json_data):
        """
        Save given data into the db file in JSON format.
        All errors are allowed through (ie not caught within).
        This can be: json error, file permission error or any
        other error writing the file.
        """
        fp = open(self._backup_path, "w")
        try:
            json.dump(
                json_data,
                fp,
                indent=4,
                separators=(',', ': '),
                sort_keys=True)
        finally:
            fp.close()
        os.rename(self._backup_path, self._path)
