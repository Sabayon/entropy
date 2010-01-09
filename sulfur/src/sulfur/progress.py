#!/usr/bin/python2 -O
# -*- coding: utf-8 -*-
#    Sulfur (Entropy Interface)
#    Copyright: (C) 2007-2009 Fabio Erculiani < lxnay<AT>sabayonlinux<DOT>org >
#
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.

from entropy.const import const_convert_to_unicode
import gobject
import gtk
from sulfur.setup import cleanMarkupString

class _Total:

    def __init__(self, widget):
        self.progress = widget
        self.steps = []
        self.nowProgres = 0.0
        self.numSteps = 0
        self.currentStep = 0
        self.stepError = False
        self.lastFrac = -1
        self.clear()

    def setup(self, steps):
        self.steps = steps
        self.numSteps = len(steps)
        self.currentStep = 0
        self.nowProgress = 0.0
        self.stepError = False
        self.clear()

    def hide(self):
        self.progress.hide()

    def show(self):
        self.progress.show()

    def next(self):
        now = 0.0
        if self.currentStep < self.numSteps:
            self.currentStep += 1
            for i in range(0, self.currentStep):
                now += self.steps[i]
                self.nowProgress = now
                self.setAbsProgress(now)
            return True
        return False

    def _percent(self, total, now):
        if total == 0:
            return 0
        return (now*100)/total

    def clear(self):
        self.progress.set_fraction(0)
        self.progress.set_text(" ")
        self.lastFrac = -1

    def setProgress(self, now, total, prefix = None):
        relStep = float(now)/float(total)
        curStep = self.steps[self.currentStep]
        absStep = curStep * relStep
        absProgress = self.nowProgress + absStep
        self.setAbsProgress(absProgress, prefix)

    def setAbsProgress(self, now, prefix = None):
        if (now == self.lastFrac) or (now >= 1.0) or (now < 0.0):
            return
        self.gtk_loop()
        self.lastFrac = now+0.01
        percent = int(self._percent(1, now))
        self.progress.set_fraction(now)
        if prefix:
            text = "%s : %3i%%" % (prefix, percent)
        else:
            text = "%3i%%" % (percent,)
        self.progress.set_text(text)

    def gtk_loop(self):
        while gtk.events_pending():
           gtk.main_iteration()

class Base:

    def __init__(self, ui, set_page_func, parent):
        self.ui = ui
        self.set_page_func = set_page_func
        self.parent = parent
        self.ui.progressMainLabel.set_text("")
        self.ui.progressSubLabel.set_text("")
        self.ui.progressExtraLabel.set_text("")
        self.total = _Total(self.ui.totalProgressBar)
        self.ui.progressBar.set_fraction(0)
        self.ui.progressBar.set_text(" ")
        self.lastFrac = -1

    def show(self):
        def run():
            self.ui.progressBox.show()
            self.set_page_func('output')
            self.lastFrac = -1
            return False
        gobject.idle_add(run)

    def reset_progress(self):
        def run():
            self.lastFrac = -1
            self.ui.progressBar.set_fraction(0)
            self.ui.progressBar.set_text(" ")
            return False
        gobject.idle_add(run)

    def hide(self, clean=False):
        def run():
            self.ui.progressBox.hide()
            if clean:
                self.ui.progressMainLabel.set_text("")
                self.ui.progressSubLabel.set_text("")
                self.ui.progressExtraLabel.set_text("")
                self.ui.progressBar.set_fraction(0)
                self.ui.progressBar.set_text(" ")
            return False
        gobject.idle_add(run)

    def setTotal(self, now, total):
        def run(now, total):
            self.total.setProgress(now, total)
            return False
        gobject.idle_add(run, now, total)

    def set_progress(self, frac, text=None):
        def run(frac, text):
            if frac == self.lastFrac: return
            if frac > 1 or frac == 0.0: return
            if frac >= 0 and frac <= 1:
                self.ui.progressBar.set_fraction(frac)
            else:
                self.ui.progressBar.set_fraction(0)
            if text != None:
                self.ui.progressBar.set_text(text)
            self.lastFrac = frac
            self.gtk_loop()
            return False
        gobject.idle_add(run, frac, text)

    def set_text(self, text):
        def run(text):
            self.ui.progressBar.set_text(text)
            return False
        gobject.idle_add(run, text)

    def set_mainLabel(self, text):
        def run(text):
            self.ui.progressMainLabel.set_markup("<b>%s</b>" % (text,))
            self.ui.progressSubLabel.set_text("")
            self.ui.progressExtraLabel.set_text("")
            return False
        gobject.idle_add(run, text)

    def set_subLabel(self, text):
        def run(text):
            mytxt = const_convert_to_unicode(text)
            if len(mytxt) > 80:
                mytxt = mytxt[:80].strip()+"..."
            self.ui.progressSubLabel.set_markup("%s" % (cleanMarkupString(mytxt),))
            self.ui.progressExtraLabel.set_text("")
            return False
        gobject.idle_add(run, text)

    def set_extraLabel(self, text):
        def run(text):
            mytxt = const_convert_to_unicode(text)
            if len(mytxt) > 80:
                mytxt = mytxt[:80].strip()+"..."
            self.ui.progressExtraLabel.set_markup(
                "<span size=\"small\">%s</span>" % cleanMarkupString(mytxt))
            self.lastFrac = -1
            return False
        gobject.idle_add(run, text)

    def gtk_loop(self):
        while gtk.events_pending():
           gtk.main_iteration()
