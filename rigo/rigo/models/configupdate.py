# -*- coding: utf-8 -*-
"""
Copyright (C) 2012 Fabio Erculiani

Authors:
  Fabio Erculiani

This program is free software; you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation; version 3.

This program is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
details.

You should have received a copy of the GNU General Public License along with
this program; if not, write to the Free Software Foundation, Inc.,
51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA
"""
import os
import subprocess

from threading import Semaphore

from gi.repository import Gtk, GLib

from rigo.utils import escape_markup, prepare_markup, open_editor
from rigo.ui.gtk3.widgets.notifications import NotificationBox

from entropy.const import const_file_writable
from entropy.i18n import _
from entropy.misc import ParallelTask


class ConfigUpdate(object):

    def __init__(self, source, metadata, rigo_service, nc):
        self._source = source
        self._metadata = metadata
        self._service = rigo_service
        self._nc = nc

    def __str__(self):
        """
        String representation of ConfigUpdate object
        """
        return "ConfigUpdate{%s, %s}" % (
            self._source, self._metadata)

    def source(self):
        """
        Return source file path (pointer to proposed
        configuration file).
        """
        return self._source

    def destination(self):
        """
        Return destination file path (pointer to file
        to be replaced).
        """
        return self._metadata['destination']

    def root(self):
        """
        Return current ROOT prefix (usually "").
        """
        return self._metadata['root']

    def apps(self):
        """
        Return the list of package identifiers owning the
        destination file.
        """
        return self._metadata['apps']

    def _ignore_remove(self, path):
        """
        Remove path without caring
        """
        try:
            os.remove(path)
        except OSError:
            pass

    def _save_back(self, proc, path):
        """
        Save back edited file once process completes
        """
        exit_st = proc.wait()
        if exit_st != os.EX_OK:
            return

        saved = self._service.save_configuration_source(
            self.source(), path)
        if not saved:
            self._ignore_remove(path)

            def _notify():
                msg = "%s: %s" % (
                    _("Cannot save configuration file"),
                    self.source(),)
                box = NotificationBox(
                    escape_markup(msg),
                    message_type=Gtk.MessageType.ERROR,
                    context_id="ConfigUpdateErrorContextId")
                self._nc.append(box)
            GLib.idle_add(_notify)

    def edit(self):
        """
        Edit the source file. Return True if edit is successful,
        False otherwise.
        """
        sem_data = {
            'sem': Semaphore(0),
            'res': None,
            'exc': None,
        }

        def _edit_handler(path):
            try:
                if path == "":
                    sem_data['res'] = False
                    return

                if not const_file_writable(path):
                    sem_data['res'] = False
                    return

                proc = open_editor(path)
                if proc is None:
                    self._ignore_remove(path)
                    sem_data['res'] = False
                    return

                task = ParallelTask(self._save_back, proc, path)
                task.name = "Edit-%s" % (self,)
                task.daemon = True
                task.start()
                sem_data['res'] = True

            except Exception as exc:
                sem_data['exc'] = exc
            finally:
                sem_data['sem'].release()

        def _error_handler(*args):
            sem_data['res'] = False
            sem_data['sem'].release()

        self._service.view_configuration_source(
            self.source(),
            reply_handler=_edit_handler,
            error_handler=_error_handler)

        sem_data['sem'].acquire()
        if sem_data['exc'] is not None:
            raise sem_data['exc']
        return sem_data['res']

    def diff(self):
        """
        Request diff between proposed source file and destination file.
        Return True if diff editor is spawned successfully, False
        otherwise.
        """
        sem_data = {
            'sem': Semaphore(0),
            'res': None,
            'exc': None,
        }

        def _diff_handler(path):
            try:
                if path == "":
                    sem_data['res'] = False
                    return

                if not const_file_writable(path):
                    sem_data['res'] = False
                    return

                proc = open_editor(path)
                if proc is None:
                    self._ignore_remove(path)
                    sem_data['res'] = False
                    return

                task = ParallelTask(proc.wait)
                task.name = "Diff-%s" % (self,)
                task.daemon = True
                task.start()
                sem_data['res'] = True

            except Exception as exc:
                sem_data['exc'] = exc
            finally:
                sem_data['sem'].release()

        def _error_handler(*args):
            try:
                sem_data['res'] = False
            finally:
                sem_data['sem'].release()

        self._service.diff_configuration(
            self.source(),
            reply_handler=_diff_handler,
            error_handler=_error_handler)

        sem_data['sem'].acquire()
        if sem_data['exc'] is not None:
            raise sem_data['exc']
        return sem_data['res']

    def discard(self):
        """
        Discard the proposed source configuration file.
        """
        sem_data = {
            'sem': Semaphore(0),
            'res': None,
            'exc': None,
        }

        def _action_handler(outcome):
            try:
                sem_data['res'] = outcome
            except Exception as exc:
                sem_data['exc'] = exc
            finally:
                sem_data['sem'].release()

        def _error_handler(*args):
            try:
                sem_data['res'] = False
            except Exception as exc:
                sem_data['exc'] = exc
            finally:
                sem_data['sem'].release()

        self._service.discard_configuration(
            self.source(),
            reply_handler=_action_handler,
            error_handler=_error_handler)

        sem_data['sem'].acquire()
        if sem_data['exc'] is not None:
            raise sem_data['exc']
        return sem_data['res']

    def merge(self):
        """
        Merge the proposed source configration file into destination.
        """
        sem_data = {
            'sem': Semaphore(0),
            'res': None,
            'exc': None,
        }

        def _action_handler(outcome):
            try:
                sem_data['res'] = outcome
            except Exception as exc:
                sem_data['exc'] = exc
            finally:
                sem_data['sem'].release()

        def _error_handler(*args):
            try:
                sem_data['res'] = False
            except Exception as exc:
                sem_data['exc'] = exc
            finally:
                sem_data['sem'].release()

        self._service.merge_configuration(
            self.source(),
            reply_handler=_action_handler,
            error_handler=_error_handler)

        sem_data['sem'].acquire()
        if sem_data['exc'] is not None:
            raise sem_data['exc']
        return sem_data['res']

    def get_markup(self):
        """
        Return ConfigurationUpdate markup text.
        """
        source = escape_markup(self.root() + self.source())
        dest = escape_markup(self.root() + self.destination())
        apps = self.apps()

        msg = "<b>%s</b>\n<small><u>%s</u>: <i>%s</i></small>" % (
            source, _("Destination"), dest)
        if apps:
            apps_msg = "\n<small><u>%s</u>: %s</small>" % (
                _("Applications"),
                ", ".join(["<i>" + x.name + "</i>" for x in apps]),)
            msg += apps_msg
        return prepare_markup(msg)
