import os
import sys
import tempfile
import pyfits

from log import msg

class FrameConfig(object):
    '''Frame configuration. 

    Each :class:`FrameConfig` object stores information about one the data
    type a recipe can process. They are used for defining the calibration
    files. However, since this information is not generally provided by CPL
    recipes, it contains only dummy information, except for the MUSE recipes.

    The objects stores a frame tag, a unique identifier for a certain kind of
    frame, the minimum and maximum number of frames needed.

    Attributes:

    .. attribute:: tag 

       Category tag name. The tag name is used to distinguish between
       different types of files. An examples of tag names is 'MASTER_BIAS'
       which specifies the master bias calibration file(s).

    .. attribute:: min

       Minimal number of frames, or :attr:`None` if not specified. A frame is
       required if the :attr:`min` is set to a value greater than 0.

    .. attribute:: max 

       Maximal number of frames, or :attr:`None` if not specified
    '''
    def __init__(self, tag, min_frames = 0, max_frames = 0, frames = None):
        self.tag = tag
        self.min = min_frames if min_frames > 0 else None
        self.max = max_frames if max_frames > 0 else None
        self.frames = frames
        self.__doc__ = self._doc()

    def extend_range(self, min_frames, max_frames):
        if self.min is not None:
            self.min = min(self.min, min_frames) if min_frames is not None \
                else None
        if self.max is not None:
            self.max = max(self.max, max_frames) if max_frames is not None \
                else None

    def set_range(self, min_frames, max_frames):
        self.min = min_frames
        self.max = max_frames

    def __str__(self):
        return str(self.frames)

    def __repr__(self):
        return "FrameDef('%s', frames=%s)" % (
            self.tag, self.frames.__repr__())

    def _doc(self):
        if self.max == 1:
            r = ' one frame'
        elif self.min > 1 and self.max > self.min:
            r = ' list of %i-%i frames' % (self.min, self.max)
        elif self.max > 1:
            r = ' one frame or list of max. %i frames' % self.max
        elif self.min > 1:
            r = ' list of min. %i frames' % self.max
        else:
            r = ' one frame or list of frames'
        if not self.min:
            r += ' (optional)'
        return r
    

class FrameList(object):
    def __init__(self, recipe, other = None):
        self._recipe = recipe
        if isinstance(other, self.__class__):
            self._values = dict((o.tag, FrameConfig(o.tag, o.min, o.max, frames=o.frames)) 
                                for o in other)
        elif isinstance(other, dict):
            self._values = dict((o[0], FrameConfig(o[0], frames=o[1])) 
                                for o in other.items())
        elif other:
            self._values = dict((o[0], FrameConfig(o[0], frames=o[1])) for o in other)
        else:
            self._values = dict()

    def _cpl_dict(self):
        cpl_frameconfigs = self._recipe._recipe.frameConfig()
        if cpl_frameconfigs is None:
            return None
        s = dict()
        for configs in cpl_frameconfigs:
            c_cfg = configs[1]
            for f in c_cfg:
                if f[0] in s:
                    s[f[0]].extend_range(f[1], f[2])
                elif f[0] in self._values:
                    s[f[0]] = self._values[f[0]]
                    s[f[0]].set_range(f[1], f[2])
                else:
                    s[f[0]] = FrameConfig(f[0], f[1], f[2])
                    self._values[f[0]] = s[f[0]]
        return s

    def _get_dict(self):
        return self._cpl_dict() or self._values

    _dict = property(_get_dict)

    def __iter__(self):
        return self._get_dict().itervalues()

    def __getitem__(self, key):
        return self._get_dict()[key]

    def __setitem__(self, key, value):
        d = self._cpl_dict()
        if d is not None:
            d[key].frames = value
        else:
            self._values.setdefault(key, FrameConfig(key)).frames = value

    def __delitem__(self, key):
        del self._get_dict()[key].frames

    def __contains__(self, key):
        return key in self._get_dict()

    def __len__(self):
        return len(self._get_dict())
        
    def __getattr__(self, key):
        return self[key]

    def __setattr__(self, key, value):
        if key.startswith('_'):
            super(FrameList, self).__setattr__(key, value)
        else:
            self[key] = value

    def __delattr__(self, key):
        del self[key]

    def __dir__(self):
        return self._get_dict().keys()

    def __repr__(self):
        return list(self).__repr__()

    def _doc(self):
        r = 'Frames for recipe %s.\n\nAttributes:\n' % (
            self._recipe.name)
        for s in self:
            r += '%s: %s\n' % (self._key(s), s.__doc__)
        return r        
    __doc__ = property(_doc)

    def _aslist(self, **ndata):
        frames = dict()
        for f in self:
            frames[f.tag] = ndata[f.tag] if f.tag in ndata else f.frames
        return list(frames.iteritems())

def mkabspath(frames, tmpdir):
    '''Convert all filenames in the frames list into absolute paths.

    :class:`pyfits.HDUList`s will be converted to temporary files located in
    the temporary directory tmpdir.

    The replacement is done in-place. The function will return the list of
    temporary files.

    param frames: :class:`list` of (tag, frame) tuples with frame being either
                  a file name or a HDU list.

    param tmpdir: directory where the temporary files are being created.
    '''
    
    tmpfiles = list()
    for i, frame in enumerate(frames):
        if isinstance(frame[1], pyfits.HDUList):
            tmpf = tempfile.mkstemp(prefix = '%s-' % frame[0],  
                                    suffix = '.fits', dir = tmpdir)
            os.close(tmpf[0])
            filename = os.path.abspath(tmpf[1])
            frames[i] = ( frame[0], filename )
            tmpfiles.append(filename)
            frame[1].writeto(filename)
        else:
            frames[i] = ( frame[0], os.path.abspath(frame[1]) )
    return tmpfiles

def expandframelist(frames):
    '''Convert a dictionary with frames into a frame list where each frame
    gets its own entry in the form (tag, frame)
    '''
    framelist = list()
    for tag, f in frames:
        if isinstance(f, list) and not isinstance(f, pyfits.HDUList):
            framelist += [ (tag, frame) for frame in f ]
        elif f is not None:
            framelist.append((tag, f))
    return framelist

class Result(object):
    def __init__(self, recipedefs, dir, res, delete = True, input_len = 0):
        '''Build an object containing all result frames.

        Calling :meth:`cpl.Recipe.__call__` returns an object that contains
        all result ('production') frames in attributes. All results for one
        tag are summarized in one attribute of the same name. 

        The attribute content is either a :class:`pyfits.HDUList` or a
        class:`list` of HDU lists, depending on the recipe and the call: If
        the recipe produces one out put frame of a tag per input file, the
        attribute contains a list if the recipe was called with a list, and if
        the recipe was called with a single input frame, the result attribute
        will also contain a single input frame. If the recipe combines all
        input frames to one output frame, a single :class:`pyfits.HDUList` es
        returned, independent of the input parameters. 

        .. todo:: This behaviour is made on some heuristics based on the
           number and type of the input frames. The heuristics will go wrong
           if there is only one input frame, specified as a list, but the
           recipe tries to summarize the input. In this case, the attribute
           will contain a list where a single :class:`pyfits.HDUList` was
           expected. To solve this problem, the "MASTER" flag has to be
           forwarded from the (MUSE) recipe which means that it should be
           exported by the recipe -- this is a major change since it probably
           leads into a replacement of CPLs recipeconfig module by something
           more sophisticated. And this is not usable for non-MUSE recipes
           anyway. So, we will skip this to probably some distant future.
        '''
        self.dir = dir
        if res[0]:
            msg.info("Result frames:" )
            msg.indent_more()
            for tag, frame in res[0]:
                msg.info("%s = %s" % (tag, frame))
            msg.indent_less()
        
        if res[1][0]:
            raise CplError(res[1][0], res[1][1], res[1][2], 
                           res[1][3], res[1][4])
        self.tags = set()
        for tag, frame in res[0]:
            hdu = pyfits.open(os.path.abspath(os.path.join(dir, frame)))
            if delete:
                os.remove(os.path.join(dir, frame))
            tag = tag
            if tag not in self.__dict__:
                self.__dict__[tag] = hdu if input_len != 1 else [ hdu ]
                self.tags.add(tag)
            elif isinstance(self.__dict__[tag], pyfits.HDUList):
                self.__dict__[tag] = [ self.__dict__[tag], hdu ]
            else:
                self.__dict__[tag].append(hdu)
        self.stat = Stat(res[2])

class Stat(object):
    def __init__(self, stat):
        self.user_time = stat[0]
        self.sys_time = stat[1]
        self.memory_is_empty = { -1:None, 0:False, 1:True }[stat[2]]


class CplError(StandardError):
    '''Error message from the recipe.

    If the CPL recipe invocation returns an error, it is converted into a
    :class:`cpl.CplError` exception and no frames are returned. Also, the
    error is notified in the log file.

    The exception is raised on recipe invocation, or when accessing the result
    frames if the recipe was started in background (:attr:`cpl.Recipe.threaded` set to 
    :attr:`True`).

    Attributes:

    .. attribute:: code

       The CPL error code returned from the recipe.

    .. attribute:: msg

       The supplied error message. 
    
    .. attribute:: filename

       The source file name where the error occurred.

    .. attribute:: line

       The line number where the error occurred.

    '''
    def __init__(self, code, txt, filename, line, function):
        msg.error("%s:%i in %s(): %s" % (filename, line, function, txt))
        self.code = code
        self.msg = txt
        self.file = filename
        self.line = line
        self.function = function
    
    def __str__(self):
        return repr("%s (%i) in %s() (%s:%s)" % (self.msg, self.code, 
                                               self.function, self.file, 
                                               self.line))

