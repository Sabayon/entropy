# -*- coding: utf-8 -*-
"""
Copyright (C) 2009 Canonical
Copyright (C) 2012 Fabio Erculiani

Authors:
  Michael Vogt
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

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk


from math import sin, cos

# pi constants
from math import pi as PI
PI_OVER_180 =   PI/180


def radian(deg):
    return PI_OVER_180 * deg

# directional shapes

class Shape(object):

    """ Base class for a Shape implementation.

        Currently implements a single method <layout> which is called
        to layout the shape using cairo paths.  It can also store the
        'direction' of the shape which should be on of the Gtk.TEXT_DIR
        constants.  Default 'direction' is Gtk.TextDirection.LTR.

        When implementing a Shape, there are two options available.

        If the Shape is direction dependent, the Shape MUST
        implement <_layout_ltr> and <_layout_rtl> methods.

        If the Shape is not direction dependent, then it simply can
        override the <layout> method.

        <layout> methods must take the following as arguments:

        cr :    a CairoContext
        x  :    x coordinate
        y  :    y coordinate
        w  :    width value
        h  :    height value

        <layout> methods can then be passed Shape specific
        keyword arguments which can be used as draw-time modifiers.
    """

    def __init__(self, direction):
        self.direction = direction
        return

    def layout(self, cr, x, y, w, h, *args, **kwargs):
        if self.direction != Gtk.TextDirection.RTL:
            self._layout_ltr(cr, x, y, w, h, *args, **kwargs)
        else:
            self._layout_rtl(cr, x, y, w, h, *args, **kwargs)
        return


class ShapeRoundedRectangle(Shape):

    """
        RoundedRectangle lays out a rectangle with all four corners
        rounded as specified at the layout call by the keyword argument:

        radius :    an integer or float specifying the corner radius.
                    The radius must be > 0.

        RoundedRectangle is not direction sensitive.
    """

    def __init__(self, direction=Gtk.TextDirection.LTR):
        Shape.__init__(self, direction)
        return

    def layout(self, cr, x, y, w, h, *args, **kwargs):
        r = kwargs['radius']

        cr.new_sub_path()
        cr.arc(r+x, r+y, r, PI, 270*PI_OVER_180)
        cr.arc(w-r, r+y, r, 270*PI_OVER_180, 0)
        cr.arc(w-r, h-r, r, 0, 90*PI_OVER_180)
        cr.arc(r+x, h-r, r, 90*PI_OVER_180, PI)
        cr.close_path()
        return


class ShapeRoundedRectangleIrregular(Shape):

    """
        RoundedRectangleIrregular lays out a rectangle for which each
        individual corner can be rounded by a specific radius,
        as specified at the layout call by the keyword argument:

        radii : a 4-tuple of ints or floats specifying the radius for
                each corner.  A value of 0 is acceptable as a radius, it
                will result in a squared corner.

        RoundedRectangleIrregular is not direction sensitive.
    """

    def __init__(self, direction=Gtk.TextDirection.LTR):
        Shape.__init__(self, direction)
        return

    def layout(self, cr, x, y, w, h, *args, **kwargs):
        nw, ne, se, sw = kwargs['radii']

        cr.save()
        cr.translate(x, y)
        if nw:
            cr.new_sub_path()
            cr.arc(nw, nw, nw, PI, 270 * PI_OVER_180)
        else:
            cr.move_to(0, 0)
        if ne:
            cr.arc(w-ne, ne, ne, 270 * PI_OVER_180, 0)
        else:
            cr.rel_line_to(w-nw, 0)
        if se:
            cr.arc(w-se, h-se, se, 0, 90 * PI_OVER_180)
        else:
            cr.rel_line_to(0, h-ne)
        if sw:
            cr.arc(sw, h-sw, sw, 90 * PI_OVER_180, PI)
        else:
            cr.rel_line_to(-(w-se), 0)

        cr.close_path()
        cr.restore()
        return


class ShapeStartArrow(Shape):

    def __init__(self, direction=Gtk.TextDirection.LTR):
        Shape.__init__(self, direction)
        return

    def _layout_ltr(self, cr, x, y, w, h, *args, **kwargs):
        aw = kwargs['arrow_width']
        r = kwargs['radius']

        cr.new_sub_path()
        cr.arc(r+x, r+y, r, PI, 270*PI_OVER_180)
        # arrow head
        cr.line_to(w-aw, y)
        cr.line_to(w-x+1, (h+y)/2)
        cr.line_to(w-aw, h)
        cr.arc(r+x, h-r, r, 90*PI_OVER_180, PI)
        cr.close_path()
        return

    def _layout_rtl(self, cr, x, y, w, h, *args, **kwargs):
        aw = kwargs['arrow_width']
        r = kwargs['radius']

        cr.new_sub_path()
        cr.move_to(x, (h+y)/2)
        cr.line_to(aw, y)
        cr.arc(w-r, r+y, r, 270*PI_OVER_180, 0)
        cr.arc(w-r, h-r, r, 0, 90*PI_OVER_180)
        cr.line_to(aw, h)
        cr.close_path()
        return


class ShapeMidArrow(Shape):

    def __init__(self, direction=Gtk.TextDirection.LTR):
        Shape.__init__(self, direction)
        return

    def _layout_ltr(self, cr, x, y, w, h, *args, **kwargs):
        aw = kwargs['arrow_width']

        cr.move_to(x, y)
        # arrow head
        cr.line_to(w-aw, y)
        cr.line_to(w-x+1, (h+y)/2)
        cr.line_to(w-aw, h)
        cr.line_to(x, h)
        cr.close_path()
        return

    def _layout_rtl(self, cr, x, y, w, h, *args, **kwargs):
        aw = kwargs['arrow_width']

        cr.move_to(x, (h+y)/2)
        cr.line_to(aw, y)
        cr.line_to(w, y)
        cr.line_to(w, h)
        cr.line_to(aw, h)
        cr.close_path()
        return


class ShapeEndCap(Shape):

    def __init__(self, direction=Gtk.TextDirection.LTR):
        Shape.__init__(self, direction)
        return

    def _layout_ltr(self, cr, x, y, w, h, *args, **kwargs):
        r = kwargs['radius']
        aw = kwargs['arrow_width']

        cr.move_to(x-1, y)
        cr.arc(w-r, r+y, r, 270*PI_OVER_180, 0)
        cr.arc(w-r, h-r, r, 0, 90*PI_OVER_180)
        cr.line_to(x-1, h)
        cr.line_to(x+aw, (h+y)/2)
        cr.close_path()
        return

    def _layout_rtl(self, cr, x, y, w, h, *args, **kwargs):
        r = kwargs['radius']

        cr.arc(r+x, r+y, r, PI, 270*PI_OVER_180)
        cr.line_to(w, y)
        cr.line_to(w, h)
        cr.arc(r+x, h-r, r, 90*PI_OVER_180, PI)
        cr.close_path()
        return


class Circle(Shape):

    def __init__(self, direction=Gtk.TextDirection.LTR):
        Shape.__init__(self, direction)
        return

    @staticmethod
    def layout(cr, x, y, w, h, *args, **kwargs):
        cr.new_path()

        r = min(w, h)*0.5
        x += int((w-2*r)/2)
        y += int((h-2*r)/2)

        cr.arc(r+x, r+y, r, 0, 360*PI_OVER_180)
        cr.close_path()
        return


class ShapeStar(Shape):

    def __init__(self, points, indent=0.61, direction=Gtk.TextDirection.LTR):
        self.coords = self._calc_coords(points, 1-indent)

    def _calc_coords(self, points, indent):
        coords = []
        step = radian(180.0/points)

        for i in range(2*points):
            if i%2:
                x = (sin(step*i)+1)*0.5
                y = (cos(step*i)+1)*0.5
            else:
                x = (sin(step*i)*indent+1)*0.5
                y = (cos(step*i)*indent+1)*0.5

            coords.append((x,y))
        return coords

    def layout(self, cr, x, y, w, h):
        points = [ (sx_sy[0]*w+x,sx_sy[1]*h+y) for sx_sy in self.coords ]
        cr.move_to(*points[0])

        for p in points[1:]:
            cr.line_to(*p)

        cr.close_path()
        return

