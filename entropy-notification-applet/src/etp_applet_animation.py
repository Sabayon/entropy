# This file is a portion of the Red Hat Network Panel Applet
#
# Copyright (C) 1999-2002 Red Hat, Inc. All Rights Reserved.
# Distributed under GPL version 2.
#
# Author: Chip Turner
#
# def help added by Tammy Fox
#
# $Id: rhn_applet_animation.py,v 1.3 2002/09/02 22:26:11 cturner Exp $

import gtk
import gtk.gdk
import math
import os
from spritz_setup import const

class rhnAppletIconPixbuf:
    def __init__(self):
        self.images = {}
    def add_file(self, name, filename):
        if not self.images.has_key(name):
            self.images[name] = []

        filepath = const.PIXMAPS_PATH + "/applet/" + filename
        if not os.path.isfile(filepath):
            filename = "../../gfx/applet/" + filename
        else:
            filename = filepath

        if not os.access(filename, os.R_OK):
            raise Exception,"Cannot open image file %s" % filename

        pixbuf = gtk.gdk.pixbuf_new_from_file(filename)

        self.add(name, pixbuf)
    def add(self, name, pixbuf):
        self.images[name].append(pixbuf)

    # find image closest to the requested size.  will be scaled later...
    def best_match(self, name, size):
        best = None

        for image in self.images[name]:
            if not best:
                best = image
                continue
            if abs(size - image.height) < abs(size - best.height):
                best = image

        return best

class rhnAppletAnimation:
    def __init__(self):
        self.frames = []
        self.cycle_frames = []

        self.frame = 0
        self.direction = 1

        # final frame is a PUBLIC DATA MEMBER... yeah, naughty
        self.final_frame = None

    def append_frames(self, frames):
        self.frames = self.frames + frames
        self.final_frame = self.frames[-1]

    def append_cycle(self, frames):
        self.cycle_frames = self.cycle_frames + frames

    def next_frame(self):
        if len(self.frames):
            return self.frames.pop(0)

        if len(self.cycle_frames):
            ret = self.cycle_frames[self.frame]
            self.frame = self.frame + self.direction

            if self.frame < 0 or self.frame >= len(self.cycle_frames):
                # oops, we moved too far.  change direction, undo last move
                self.direction = -self.direction
                self.frame = self.frame + self.direction

            return ret

        return None

def alpha_tween(start_image, end_image, steps):
    tmp = start_image.copy() #start_image.scale_simple(end_image.get_width(), end_image.get_height(), gtk.gdk.INTERP_BILINEAR)

    frames = [ start_image ]
    stepsize = 256/steps

    for i in range(2, steps):
        buf = tmp.copy()

        end_image.composite(buf,
                            # dest x, y, w, h
                            0, 0, buf.get_width(), buf.get_height(),
                            # ofset x, y
                            0, 0,
                            # scale factor x, y
                            1.0, 1.0,
                            gtk.gdk.INTERP_BILINEAR,
                            i * stepsize - 1)

        frames.append(buf)

    frames.append(end_image)

    return frames
