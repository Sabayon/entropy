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

import gobject

class _SulfurSignals(gobject.GObject):

    def __init__(self):
        gobject.GObject.__init__(self)

gobject.type_register(_SulfurSignals)
gobject.signal_new("ugc_data_update", _SulfurSignals, gobject.SIGNAL_RUN_FIRST,
                   gobject.TYPE_NONE, ())
gobject.signal_new("install_queue_empty", _SulfurSignals, gobject.SIGNAL_RUN_FIRST,
                   gobject.TYPE_NONE, ())
gobject.signal_new("install_queue_filled", _SulfurSignals, gobject.SIGNAL_RUN_FIRST,
                   gobject.TYPE_NONE, ())
gobject.signal_new("install_queue_changed", _SulfurSignals, gobject.SIGNAL_RUN_FIRST,
                   gobject.TYPE_NONE, (int,))

SulfurSignals = _SulfurSignals()
