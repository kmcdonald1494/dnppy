__author__ = 'jwely'

import os

def create_outname(outdir, inname, suffix, ext = False):
    """
    Quick way to create unique output filenames within iterative functions

     This function is built to simplify the creation of output filenames. Function allows
     outdir = False and will create an outname in the same directory as inname. Function will
     add a the user input suffix, separated by an underscore "_" to generate an output name.
     this is usefull when performing a small modification to a file and saving new output with
     a new suffix. function returns an output name, it does not save the file as that name.


     Inputs:
       outdir      either the directory of the desired outname or False to create an outname
                   in the same directory as the inname
       inname      the input file from which to generate the output name "outname"
       suffix      suffix to attach to the end of the filename to mark it as output
       ext         specify the file extension of the output filename. Leave blank or False
                   and the outname will inherit the same extension as inname

     Example Usage:
       outdir = r"C:\Users\jwely\Desktop\output"
       inname = r"C:\Users\jwely\Desktop\folder\subfolder\Landsat_tile.tif"
       suffix = "adjusted"
       outname = core.create_outname(outdir,inname,suffix)

       will set outname equal to "C:\Users\jwely\Desktop\output\Landsat_tile_adjusted.tif" which
       can be passed to other functions that require an output filepath.
    """

    # remove unneeded . in the extension
    ext = ext.replace(".","")

    # isolate the filename from its directory and extension
    if os.path.isfile(inname):
        head, tail  = os.path.split(inname)
        noext       = tail.split('.')[:-1]
        noext       ='.'.join(noext)
    else:
        tail    = inname
        if "." in inname:
            noext   = tail.split('.')[:-1]
            noext   = '.'.join(noext)
        else:
            noext   = inname

    # create the suffix
    if ext:
        suffix = "_{0}.{1}".format(suffix,ext)
    else:
        ext = tail.split('.')[-1:]
        suffix = "_{0}.{1}".format(suffix, ''.join(ext))

    if outdir:
        outname = os.path.join(outdir, noext+suffix)
        return outname
    else:
        outname = os.path.join(head, noext+suffix)
        return outname
