"""
======================================================================================
                                   dnppy.raster
======================================================================================
 This script is part of (dnppy) or "DEVELOP National Program py"
 It is maintained by the Geoinformatics YP class.

It contains functions for fairly routine manipulations of raster data.
Also see dnppy.calc for 
"""

__author__ = ["Jeffry Ely, jeff.ely.08@gmail.com",
              "Lauren Makely, lmakely09@gmail.com"]


__all__ =['to_numpy',           # complete
          'from_numpy',         # complete
          'many_stats',         # working, but incomplete
          'stack',              # complete
          'temporal_fill',      # planned development
          'find_overlap',       # complete
          'spatially_match',    # complete
          'clip_and_snap',      # complete
          'clip_to_shape',      # complete
          'define_null',        # complete
          'set_range_null',     # complete
          'grab_info',          # working, but incomplete
          'identify',           # working, but incomplete
          'is_rast',            # complete
          'enf_rastlist',       # complete
          'project_resamp',     # complete
          'show_stats']         # complete


import os, shutil, time
import matplotlib.pyplot as plt

from dnppy import core
if core.check_module('numpy'): import numpy
import arcpy

if arcpy.CheckExtension('Spatial')=='Available':
    arcpy.CheckOutExtension('Spatial')
    from arcpy import sa,env
    arcpy.env.overwriteOutput = True

#======================================================================================
def to_numpy(raster, num_type = False):

    """
    Wrapper for arcpy.RasterToNumpyArray with better metadata handling
    
     This is just a wraper for the RasterToNumPyArray function within arcpy, but it also
     extracts out all the spatial referencing information that will probably be needed
     to save the raster after desired manipulations have been performed.
     also see raster.from_numpy function in this module.

     inputs:
       Raster              Any raster suported by the arcpy.RasterToNumPyArray function
       num_type            must be a string equal to any of the types listed at the following
                           address [http://docs.scipy.org/doc/numpy/user/basics.types.html]
                           for example: 'uint8' or 'int32' or 'float32'
     outputs:
       numpy_rast          the numpy array version of the input raster
       Metadata            An object with the following attributes.
           .Xmin            the left edge
           .Ymin            the bottom edge
           .Xmax            the right edge
           .Ymax            the top edge
           .Xsize           the number of columns
           .Ysize           the number of rows
           .cellWidth       resolution in x direction
           .cellHeight      resolution in y direction
           .projection      the projection information to give the raster
           .NoData_Value    the numerical value which represents NoData in this raster

     Usage example:
       call this function with  " rast,Metadata = to_numpy(Raster) "
       perform numpy manipulations as you please
       then save the array with " raster.from_numpy(rast,Metadata,output)   "
    """

    # create a metadata object and assign attributes to it
    class metadata:

        def __init__(self, raster, xs, ys):

            self.Xsize          = xs
            self.Ysize          = ys
            
            self.cellWidth      = arcpy.Describe(raster).meanCellWidth
            self.cellHeight     = arcpy.Describe(raster).meanCellHeight
            
            self.Xmin           = arcpy.Describe(raster).Extent.XMin
            self.Ymin           = arcpy.Describe(raster).Extent.YMin
            self.Xmax           = self.Xmin + (xs * self.cellWidth)
            self.Ymax           = self.Ymin + (ys * self.cellHeight)

            self.rectangle      = ' '.join([str(self.Xmin),
                                            str(self.Ymin),
                                            str(self.Xmax),
                                            str(self.Ymax)])
            
            self.projection     = arcpy.Describe(raster).spatialReference
            self.NoData_Value   = arcpy.Describe(raster).noDataValue
            return

    # read in the raster as an array
    if is_rast(raster):

        numpy_rast  = arcpy.RasterToNumPyArray(raster)
        ys, xs      = numpy_rast.shape
        meta        = metadata(raster, xs, ys)
        
        if num_type:
            numpy_rast = numpy_rast.astype(num_type)
            
    else:  
        print("Raster '{0}'does not exist".format(raster))

    return numpy_rast, meta



def from_numpy(numpy_rast, Metadata, outpath, NoData_Value = False, num_type = False):
    """
    Wrapper for arcpy.NumPyArrayToRaster function with better metadata handling
    
     this is just a wraper for the NumPyArrayToRaster function within arcpy. It is used in
     conjunction with to_numpy to streamline reading image files in and out of numpy
     arrays. It also ensures that all spatial referencing and projection info is preserved
     between input and outputs of numpy manipulations.

     inputs:
       numpy_rast          the numpy array version of the input raster
       Metadata            The variable exactly as output from "to_numpy"
       outpath             output filepath of the individual raster
       NoData_Value        the no data value of the output raster
       num_type            must be a string equal to any of the types listed at the following
                           address [http://docs.scipy.org/doc/numpy/user/basics.types.html]
                           for example: 'uint8' or 'int32' or 'float32'

     Usage example:
       call to_numpy with  "rast,Metadata = to_numpy(Raster)"
       perform numpy manipulations as you please
       then save the array with "raster.from_numpy(rast, Metadata, output)"
    """

    if num_type:
        numpy_rast = numpy_rast.astype(num_type)

    if not NoData_Value:
        NoData_Value = Metadata.NoData_Value
            
    llcorner = arcpy.Point(Metadata.Xmin, Metadata.Ymin)
    
    # save the output.
    OUT = arcpy.NumPyArrayToRaster(numpy_rast, llcorner, Metadata.cellWidth ,Metadata.cellHeight)
    OUT.save(outpath)

    # define its projection
    try:
        arcpy.DefineProjection_management(outpath, Metadata.projection)
    except:
        pass

    # reset the NoData_Values
    try:
        arcpy.SetRasterProperties_management(outpath, data_type="#", nodata = "1 " + str(NoData_Value))
    except:
        pass
    
    # do statistics and pyramids
    arcpy.CalculateStatistics_management(outpath)
    arcpy.BuildPyramids_management(outpath)
    
    print("Saved output file as {0}".format(outpath))

    return


def many_stats(rasterlist, outdir, outname, saves = ['AVG','NUM','STD'],
                                   low_thresh = None, high_thresh = None):
    """
    Take statitics across many input rasters
    
     this function is used to take statistics on large groups of rasters with identical
     spatial extents. Similar to Rolling_Raster_Stats

     Inputs:
        rasterlist      list of raster filepaths for which to take statistics
        outdir          Directory where output should be stored.
        saves           which statistics to save in a raster. In addition to the options
                        supported by 
                           
                        Defaults to all three ['AVG','NUM','STD'].
        low_thresh      values below low_thresh are assumed erroneous and set to NoData
        high_thresh     values above high_thresh are assumed erroneous and set to NoData.
    """

    if not os.path.isdir(outdir):
        os.makedirs(outdir)
    
    rasterlist = enf_rastlist(rasterlist)

    # build the empty numpy array based on size of first raster
    temp_rast, metadata = to_numpy(rasterlist[0])
    xs, ys              = temp_rast.shape
    zs                  = len(rasterlist)
    rast_3d             = numpy.zeros((xs,ys,zs))

    metadata.NoData_Value = 'nan'

    # open up the initial figure
    fig, im = make_fig(temp_rast)

    # populate the 3d matrix with values from all rasters
    for i,raster in enumerate(rasterlist):

        # print a status and open a figure
        print('working on file {0}'.format(raster))
        new_rast, new_meta  = to_numpy(raster, 'float32')
        show_stats(new_rast, fig, im)

        if not new_rast.shape == (xs,ys):
            print new_rast.shape

        # set rasters to inherit the nodata value of first raster
        if new_meta.NoData_Value != metadata.NoData_Value:
            new_rast[new_rast == new_meta.NoData_Value] = metadata.NoData_Value
            
        # set values outside thresholds to nodata values
        if not low_thresh == None:
            new_rast[new_rast < low_thresh] = metadata.NoData_Value
        if not high_thresh == None:
            new_rast[new_rast > high_thresh] = metadata.NoData_Value

        rast_3d[:,:,i] = new_rast

    # build up our statistics by masking nan values and performin matrix opperations
    rast_3d_masked  = numpy.ma.masked_array(rast_3d, numpy.isnan(rast_3d))

    if "AVG" in saves:
        avg_rast        = numpy.mean(rast_3d_masked, axis = 2)
        avg_rast        = numpy.array(avg_rast)
        show_stats(avg_rast, fig, im, "Average")
        time.sleep(2)

        avg_name = core.create_outname(outdir, outname, 'AVG', 'tif')
        print("Saving AVERAGE output raster as {0}".format(avg_name))
        from_numpy(avg_rast, metadata, avg_name)

    if "STD" in saves:
        std_rast        = numpy.std(rast_3d_masked, axis = 2)
        std_rast        = numpy.array(std_rast)
        show_stats(avg_rast, fig, im, "Standard Deviation")
        time.sleep(2)

        std_name = core.create_outname(outdir, outname, 'STD', 'tif')
        print("Saving AVERAGE output raster as {0}".format(std_name))
        from_numpy(std_rast, metadata, std_name)
        
    if "NUM" in saves:
        num_rast        = (numpy.zeros((xs,ys)) + zs) - numpy.sum(rast_3d_masked.mask, axis = 2)
        num_rast        = numpy.array(num_rast)
        show_stats(avg_rast, fig, im, "Good pixel count (NUM)")
        time.sleep(2)

        std_name = core.create_outname(outdir, outname, 'NUM', 'tif')
        print("Saving NUMBER output raster as {0}".format(std_name))
        from_numpy(num_rast, metadata, num_name)
                   
    close_fig(fig, im)

    return


def is_rast(filename):
    """ Verifies that input filenamecore.exists, and is of raster format"""

    import os
    
    rast_types=['bil','bip','bmp','bsq','dat','gif','img','jpg','jp2','png','tif',
                'BIL','BIP','BMP','BSQ','DAT','GIF','IMG','JPG','JP2','PNG','TIF']
    ext = filename[-3:]

    if os.path.isfile(filename):
        for rast_type in rast_types:
            if ext == rast_type:
                return(True)

    return(False)


          
def stack(raster_paths):
    """
    Creates 3d numpy array from multiple coincident rasters
    
    This function is to create a 3d numpy array out of multiple coincident rasters.
    Usefull for layering multiple bands in a sceen or bulding a time series "data brick".
    It is important that all layers that are stacked are perfectly coincident, having
    identical pixel dimensions, resolution, projection, and spatial referencing. 

    Inputs:
        raster_paths    list of filepaths to rasters to be stacked. They will be stacked in
                        the same order as they ar einput

    Returns:
        stack           3d numpy array containing stacked raster data
        meta            metadata of the first raster layer. All layers should have identical
                        metadata.
    """
 
    for z,raster in enumerate(raster_paths):
        temp_image, temp_meta = to_numpy(raster)

        if z==0:
            stack = numpy.zeros((len(raster_paths),temp_meta.Ysize,temp_meta.Xsize))
        
        stack[z,:,:] = temp_image
        meta = temp_meta
        print(vars(meta))
        
    return stack, meta



def find_overlap(file_A, NoData_A, file_B, NoData_B, outpath, Quiet=False):
    """
     Finds overlaping area between two raster images.
     
     this function examines two images and outputs a raster raster.identifying pixels where both
     rasters have non-NoData values. Output raster has 1's where both images have data and
     0's where one or both images are missing data.

     inputs:
       file_A      the first file
       NoData_A    the NoData value of file A
       file_B      the second file
       NoData_B    the NoData value of file B
       outpath     the output filename for the desired output. must end in ".tif"
    """
    
    # import modules
    if check_module('numpy'): import numpy
    if not raster.is_rast(file_A) or not raster.is_rast(file_B):
        print '{raster.find_overlap} both inputs must be rasters!'

    # spatially match the rasters
    print '{raster.find_overlap} preparing input rasters!'
    raster.clip_and_snap(file_A,file_B,file_B,False,NoData_B)
    
    # load the rasters as numpy arays.
    a,metaA = to_numpy(file_A)
    b,metaB = to_numpy(file_B)

    Workmatrix = numpy.zeros((metaA.Ysize,metaA.Xsize))
    Workmatrix = Workmatrix.astype('uint8')

    a[(a >= NoData_A * 0.99999) & (a <= NoData_A * 1.00001)] = int(1)
    b[(b >= NoData_B * 0.99999) & (b <= NoData_B * 1.00001)] = int(1)

    print 'Finding overlaping pixels!'
    Workmatrix = a + b
    Workmatrix[Workmatrix <  2] = int(0)
    Workmatrix[Workmatrix >= 2] = int(1)
                
    print 'Saving overlap file!'       
    raster.from_numpy(Workmatrix, metaA, outpath,'0','uint8',False)
    Set_Null_Values(outpath,0,False)
    arcpy.RasterToPolygon_conversion(outpath, outpath[:-4]+'.shp', 'NO_SIMPLIFY')
    
    return metaA, metaB



def spatially_match(snap_raster, rasterlist, outdir, numtype = False, NoData_Value = False,
                            resamp_type = False):
    """
    Prepares input rasters for further numerical processing
    
     This function simply ensures all rasters in "rasterlist" are identically projected
     and have the same cell size, then calls the raster.clip_and_snaps function to ensure
     that the cells are perfectly coincident and that the total spatial extents of the images
     are identical, even when NoData values are considered. This is usefull because it allows
     the two images to be passed on for numerical processing as nothing more than matrices
     of values, and the user can be sure that any index in any matrix is exactly coincident
     with the same index in any other matrix. This is especially important to use when
     comparing different datasets from different sources outside arcmap, for example MODIS
     and Landsat data with an ASTER DEM.

     inputs:
       snap_raster     raster to which all other images will be snapped
       rasterlist      list of rasters, a single raster, or a directory full of tiffs which
                       will be clipped to the extent of "snap_raster" and aligned such that
                       the cells are perfectly coincident.
       outdir          the output directory to save newly created spatially matched tifs.
       resamp_type     The resampling type to use if images are not identical cell sizes.
                           "NEAREST","BILINEAR",and "CUBIC" are the most common.
    """

    # import modules and sanitize inputs
    tempdir = os.path.join(outdir,'temp')
    import shutil
    if not os.path.isdir(outdir):
        os.makedirs(outdir)
    if not os.path.isdir(tempdir):
        os.makedirs(tempdir)
    
    rasterlist = enf_rastlist(rasterlist)
    core.exists(snap_raster)
    
    usetemp = False

    # set the snap raster environment in arcmap.
    arcpy.env.snapRaster = snap_raster

    print('Loading snap raster {0}'.format(snap_raster))
    _,snap_meta = to_numpy(snap_raster)
    print('Bounds of rectangle to define boundaries: [{0}]'.format(snap_meta.rectangle))
    
    # for every raster in the raster list, snap rasters and clip.
    for rastname in rasterlist:
        
        _,meta      = to_numpy(rastname)
        head,tail   = os.path.split(rastname)
        tempname    = os.path.join(tempdir,tail)

        if snap_meta.projection.projectionName != meta.projection.projectionName:
            print 'The files are not the same projection!'
            core.project(rastname, snap_raster, tempname, resamp_type, snap_raster)
            usetemp = True

        if round(float(snap_meta.cellHeight)/float(meta.cellHeight),5)!=1 and \
        round(float(snap_meta.cellWidth)/float(meta.cellWidth),5)!=1:

            if resamp_type:
                cell_size = "{0} {1}".format(snap_meta.cellHeight,snap_meta.cellWidth)
                arcpy.Resample_management(rastname, tempname, cell_size, resamp_type)
                usetemp = True
                
            else:
                raise Exception("images are NOT the same resolution! {0} vs {1} input a resample type!".format(
                    (snap_meta.cellHeight,snap_meta.cellWidth),(meta.cellHeight,meta.cellWidth)))
            
        # define an output name and run the Clip_ans_Snap_Raster function on formatted tifs.
        head,tail   = os.path.split(rastname)
        outname     = core.create_outname(outdir, rastname,'matched')

        # if a temporary file was created in previous steps, use that one for clip and snap               
        if usetemp:   
            clip_and_snap(snap_raster, tempname, outname, numtype, NoData_Value)
        else:
            clip_and_snap(snap_raster, rastname, outname, numtype, NoData_Value)
            
        print(' Finished matching raster!')

    shutil.rmtree(tempdir)
    return
           

def clip_and_snap(snap_raster, rastname, outname, numtype = False , NoData_Value = False):
    """
    Ensures perfect coincidence between a snap_raster and any input rasters
    
     This script is primarily intended for calling by the "raster.spatially_match" function
     but may be called independently.

     it is designed to input a reference image and a working image. The working image must
     be in exactly the same projection and spatial resolution as the reference image. This
     script will simply ensure the tif files are perfectly coincident, and that the total image
     extents are identical. This is important when performing numpy manipulations on matrices
     derived from different datasets manipulated in different ways to ensure alignment.

     This script makes modifications to the original raster file, so save a backup if you are
     unsure how to use this.

     inputs:
       snap_raster     filepath and name of reference raster whos extent will be taken on by
                       the input rastername
       rastname        name of raster file which should be snapped to the snap_raster
       NoData_Value    Value desired to represent NoData in the saved image.

     outputs:
       snap_meta       metadata of the snap_raster file as output by to_numpy
       meta            metadata of the rastername file as output by to_numpy
    """

    # grab metadata for rastname
    _,snap_meta = to_numpy(snap_raster)
    _,meta      = to_numpy(rastname)

    if not NoData_Value:
        NoData_Value = meta.NoData_Value

    if not numtype:
        numtype = 'float32'
        
    head,tail   = os.path.split(outname)
    tempdir     = os.path.join(head, 'temp')
    
    if not os.path.isdir(tempdir):
        os.makedirs(tempdir)

    # set the snap raster environment in arcmap.
    arcpy.env.snapRaster = snap_raster

    # remove data that is outside the bounding box and snap the image
    print("Clipping {0}".format(rastname))
    
    tempout = os.path.join(tempdir,tail)
    try:
        arcpy.Clip_management(rastname, snap_meta.rectangle, tempout, "#", "#", "NONE", "MAINTAIN_EXTENT")
    except:
        arcpy.Clip_management(rastname, snap_meta.rectangle, tempout, "#", "#", "NONE")
    
    # load the newly cliped raster, find the offsets
    raster, meta = to_numpy(tempout)
    xoffset      = int(round((meta.Xmin - snap_meta.Xmin)/meta.cellWidth,0))
    yoffset      = int(round((meta.Ymin - snap_meta.Ymin)/meta.cellHeight,0))

    # first iteration of clip with snap_raster environment sometimes has rounding issues
    # run clip a second time if raster does not fully lie within the extents of the bounding box
    if meta.Xsize > snap_meta.Xsize or meta.Ysize > snap_meta.Ysize:
        arcpy.Clip_management(tempout,snap_meta.rectangle, tempout[:-4] + '2.tif',"#","#","NONE")

        # reload and recalculate offsets
        raster, meta = to_numpy(tempout[:-4] + '2.tif')
        xoffset      = int(round((meta.Xmin - snap_meta.Xmin)/meta.cellWidth,0))
        yoffset      = int(round((meta.Ymin - snap_meta.Ymin)/meta.cellHeight,0))

    # plop the snaped raster into the new output raster, alter the metadata, and save it
    meta.Xmin   = snap_meta.Xmin
    meta.Ymin   = snap_meta.Ymin
    Yrange      = range(yoffset,(yoffset + meta.Ysize))
    Xrange      = range(xoffset,(xoffset + meta.Xsize))

    # create empty matrix of NoData_Values to store output
    print('Saving {0}'.format(rastname))
    newraster = numpy.zeros((snap_meta.Ysize, snap_meta.Xsize)) + float(meta.NoData_Value)
    
    print("recasting rastwer with shape ({1}) to shape ({0})".format(newraster.shape, raster.shape))

    '''print snap_meta.Ysize
    print meta.Ysize
    print yoffset
    
    print snap_meta.Xsize
    print meta.Xsize
    print xoffset'''
    
    newraster[(snap_meta.Ysize - meta.Ysize - yoffset):(snap_meta.Ysize - yoffset),
              (snap_meta.Xsize - meta.Xsize - xoffset):(snap_meta.Xsize - xoffset)] = raster[:,:]
    from_numpy(newraster, meta, outname, NoData_Value, numtype)

    # clean up
    shutil.rmtree(tempdir)
    return snap_meta,meta


def clip_to_shape(rasterlist, shapefile, outdir = False):
    """
     Simple batch clipping script to clip rasters to shapefiles. 

     Inputs:
       rasterlist      single file, list of files, or directory for which to clip rasters
       shapefile       shapefile to which rasters will be clipped
       outdir          desired output directory. If no output directory is specified, the
                       new files will simply have '_c' added as a suffix. 
    """

    rasterlist = enf_rastlist(rasterlist)

    # ensure output directorycore.exists
    if outdir and not os.path.exists(outdir):
        os.makedirs(outdir)

    for raster in rasterlist:

        # create output filename with "c" suffix
        outname = core.create_outname(outdir,raster,'c')
        
        # perform double clip , first using clip_management (preserves no data values)
        # then using arcpy.sa module which can actually do clipping geometry unlike the management tool.
        arcpy.Clip_management(raster,"#",outname,shapefile,"ClippingGeometry")
        out = sa.ExtractByMask(outname,shapefile)
        out.save(outname)
        print("Clipped and saved: {0}".format(outname))
    
    return


def define_null(filelist, NoData_Value, Quiet=False):
    """
    Simple batch NoData setting function. Makes raster data more arcmap viewing friendly
    
     Function inputs a list of raster (usually tifs) files and sets no data values. This
     function does not actually change the raster values in any way, and simply defines which
     numerical values to be considered NoData in metadata.

     inputs:
       filelist        list of files for which to set NoData values. easily created with
                       "core.list_files" function
       NoData_Value    Value to declare as NoData (usually 0 or -9999)
       Quiet           Set Quiet to 'True' if you don't want anything printed to screen.
                       Defaults to 'False' if left blank.
    """

    filelist = core.enf_rastlist(filelist)

    # iterate through each file in the filelist and set nodata values
    for filename in filelist:

        arcpy.SetRasterProperties_management(filename,data_type="#",statistics="#",
                    stats_file="#",nodata="1 "+str(NoData_Value))
        if not Quiet:
            print '{raster.define_null} Set NoData values in ' + filename
               
    if not Quiet:print '{raster.define_null} Finished! \n'            
    return



def set_range_null(filelist, above, below, NoData_Value):
    """
    Changes values within a certain range to NoData
    
     similar to raster.define_null, but can take an entire range of values to set to NoData.
     useful in filtering obviously erroneous high or low values from a raster dataset.

     inputs:
       filelist    list of files for which to set NoData values. easily created with
                       "core.list_files" function
       above       will set all values above this, but below "below" to NoData
                       set to 'False' if now upper bound exists
       below       will set all values below this, but above "above" to NoData
                       set to 'False' if no lower bound exists
    """

    # sanitize filelist input
    filelist = enf_rastlist(filelist)

    # iterate through each file in the filelist and set nodata values
    for filename in filelist:
        #load raster as numpy array and save spatial referencing.
        raster, meta = to_numpy(filename)

        if above and below:
            raster[raster <= below and raster >= above] = NoData_Value
        elif above:
            raster[raster >= above] = NoData_Value
        elif below:
            raster[raster <= below] = NoData_Value
            
        raster.from_numpy(raster, meta, filename)
        arcpy.SetRasterProperties_management(filename, data_type="#",statistics="#",
                    stats_file="#",nodata="1 "+str(NoData_Value))
        
        print("Set NoData values in {0}".format(filename))
            
    return


def temporal_fill(filelist,Quiet=False):

    """
     This function is designed to input a time sequence of rasters with partial voids and
     output a copy of each input image with every pixel equal to the last good value taken.
     This function will step forward in time through each raster and fill voids from the values
     of previous rasters. The resulting output image will contain all the data that was in the
     original image, with the voids filled with older data. A second output image will be
     generated where the pixel values are equal to the age of each pixel in the image. So
     if a void was filled with data thats 5 days old, the "age" raster will have a value of
     "5" at that location.
    """

    print 'This function will eventually be developed' 
    print 'if you need it ASAP, contact the geoinformatics Fellows!'
    
    return



def grab_info(filepath, data_type = False, CustGroupings = False):

    """
    Extracts in-filename metadata from common NASA data products

     This function simply extracts relevant sorting information from a MODIS or Landsat
     filepath of any type or product and returns object properties relevant to that data.
     it will be expanded to include additional data products in the future.

     Inputs:
           filepath        Full or partial filepath to any modis product tile
           data_type       Manually tell the software what the data is.
           CustGroupings   User defined sorting by julian days of specified bin widths.
                           input of 5 for example will group January 1,2,3,4,5 in the first bin
                           and january 6,7,8,9,10 in the second bin, etc.

     Outputs:
           info            on object containing the attributes (product, year, day, tile)
                           retrieve these values by calling "info.product", "info.year" etc.

     Attributes by data type:
           All             type,year,j_day,month,day,season,CustGroupings,suffix

           MODIS           product,tile
           Landsat         sensor,satellite,WRSpath,WRSrow,groundstationID,Version,band

     Attribute descriptions:
           type            NASA data type, for exmaple 'MODIS' and 'Landsat'
           year            four digit year the data was taken
           j_day           julian day 1 to 365 or 366 for leap years
           month           three character month abbreviation
           day             day of the month
           season          'Winter','Spring','Summer', or 'Autumn'
           CustGroupings   bin number of data according to custom group value. sorted by
                           julian day
           suffix          Any additional trailing information in the filename. used to find
                           details about special

           product         usually a level 3 data product from sensor such as MOD11A1
           tile            MODIS sinusoidal tile h##v## format

           sensor          Landsat sensor
           satellite       usually 5,7, or 8 for the landsat satellite
           WRSpath         Landsat path designator
           WRSrow          Landsat row designator
           groundstationID ground station which recieved the data download fromt he satellite
           Version         Version of landsat data product
           band            band of landsat data product, usually 1 through 10 or 11.
    """

    
    # pull the filename and path apart 
    path,name = os.path.split(filepath)
    
    # create an info object class instance
    class info_object(object):pass
    info = info_object()

    # figure out what kind of data these files are. 
    if not data_type:
        data_type = identify(name)

    if data_type == 'MODIS':
        params  =['product','year','j_day','tile','type','version','tag','suffix']
        n       = name.split('.')
        end     = n[4]
        string  =[n[0],name[9:13],name[13:16],n[2],'MODIS',n[3],end[:13],end[13:]]

    if data_type == 'MODIS':
        params  =['product','year','j_day','tile','type','version','tag','suffix']
        n       = name.split('.')
        end     = n[4]
        string  =[n[0],name[9:13],name[13:16],n[2],'MODIS',n[3],end[:13],end[13:]]
            
    elif data_type =='Landsat':
        params  =['sensor','satellite','WRSpath','WRSrow','year','j_day','groundstationID',
                                                        'Version','band','type','suffix']
        n       = name.split('.')[0]
        string  =[n[1],n[2],n[3:6],n[6:9],n[9:13],n[13:16],n[16:19],
                n[19:21],n[23:].split('_')[0],'Landsat','_'.join(n[23:].split('_')[1:])]
            
    elif data_type == 'WELD_CONUS' or data_type == 'WELD_AK':
        params  = ['coverage','period','year','tile','start_day','end_day','type']
        n       = name.split('.')
        string  =[n[0],n[1],n[2],n[3],n[4][4:6],n[4][8:11],'WELD']
        # take everything after the first underscore as a suffix if onecore.exists.
        if '_' in name:
            params.append('suffix')
            string.append('_'.join(name.split('_')[1:]))
            
    elif data_type == 'ASTER':
        params  = ['product','N','W','type','period']
        n       = name.split('_')
        string  = [n[0],n[1][1:3],n[1][5:9],n[-1].split('.')[0],'none']
    
    elif data_type == 'TRMM':
        print '{Grab_Data_Info} no support for TRMM data yet! you could add it!'
        return(False)

    elif data_type == 'AMSR_E':
        print '{Grab_Data_Info} no support for AMSR_E data yet! you could add it!'
        return(False)

    elif data_type == 'AIRS':
        print '{Grab_Data_Info} no support for AIRS data yet! you could add it!'
        return(False)

    # if data doesnt look like anything!
    else:
        print 'Data type for file ['+name+'] could not be identified as any supported type'
        print 'improve this function by adding info for this datatype!'
        return(False)

    # Create atributes and assign parameter names and values
    for i in range(len(params)):
        setattr(info,params[i],string[i])
    
    # ................................................................................
    # perform additional data gathering only if data has no info.period atribute. Images with
    # this attribute represent data that is produced from many dates, not just one day.
    if not hasattr(info,'period'):
    # fill in date format values and custom grouping and season information based on julian day
    # many files are named according to julian day. we want the date info for these files.
        try:
            tempinfo    = datetime.datetime(int(info.year),1,1)+datetime.timedelta(int(int(info.j_day)-1))
            info.month  = tempinfo.strftime('%b')
            info.day    = tempinfo.day
            
        # some files are named according to date. we want the julian day info for these files
        except:
            fmt         = '%Y.%m.%d'
            tempinfo    = datetime.datetime.strptime('.'.join([info.year,info.month,info.day]),fmt)
            info.j_day  = tempinfo.strftime('%j')

    # fill in the seasons by checking the value of julian day
        if int(info.j_day) <=78 or int(info.j_day) >=355:
            info.season='Winter'
        elif int(info.j_day) <=171:
            info.season='Spring'
        elif int(info.j_day)<=265:
            info.season='Summer'
        elif int(info.j_day)<=354:
            info.season='Autumn'
        
    # bin by julian day if integer group width was input
    if CustGroupings:
        CustGroupings=core.enf_list(CustGroupings)
        for grouping in CustGroupings:
            if type(grouping)==int:
                groupname='custom' + str(grouping)
                setattr(info,groupname,1+(int(info.j_day)-1)/(grouping))
            else:
                print('{Grab_Data_Info} invalid custom grouping entered!')
                print('{Grab_Data_Info} [CustGrouping] must be one or more integers in a list')

    # make sure the filepath input actually leads to a real file, then give user the info
    if core.exists(filepath):
        if not Quiet:
            print '{Grab_Data_Info} '+ info.type + ' File ['+ name +'] has attributes '
            print vars(info)
        return(info)
    else:
        return(False)



def identify(name):

    """
    Compare filename against known NASA data file naming conventions to raster.identify it

     Nested within the raster.grab_info function

     Inputs:
       name        any filename of a file which is suspected to be a satellite data product

     Outputs:
       data_type   If the file is found to be of a specific data type, output a string
                   designating that type. The options are as follows, with urls for reference                          

     data_types:
           MODIS       https://lpdaac.usgs.gov/products/modis_products_table/modis_overview
           Landsat     http://landsat.usgs.gov/naming_conventions_scene_identifiers.php
           TRMM        http://disc.sci.gsfc.nasa.gov/precipitation/documentation/TRMM_README/
           AMSR_E      http://nsidc.org/data/docs/daac/ae_ocean_products.gd.html
           ASTER       http://mapaspects.org/article/matching-aster-granule-id-filenames
           AIRS        http://csyotc.cira.colostate.edu/documentation/AIRS/AIRS_V5_Data_Product_Description.pdf
           False       if no other types appear to be correct.
    """

    if  any( x==name[0:2] for x in ['LC','LO','LT','LE','LM']):
        return('Landsat')
    elif any( x==name[0:3] for x in ['MCD','MOD','MYD']):
        return('MODIS')
    elif any( x==name[0:4] for x in ['3A11','3A12','3A25','3A26','3B31','3A46','3B42','3B43']):
        return('TRMM')
    elif name[0:5]=='CONUS':
        return('WELD_CONUS')
    elif name[0:6]=='Alaska':
        return('WELD_AK')
    elif name[0:6]=='AMSR_E':
        return('AMSR_E')
    elif name[0:3]=='AST':
        return('ASTER')
    elif name[0:3]=='AIR':
        return('AIRS')

    
    else:
        return(False)


def enf_rastlist(filelist):

    """
    ensures a list of inputs filepaths contains only valid raster tyeps
    """

    # first place the input through the same requirements of any filelist
    filelist        = core.enf_filelist(filelist)
    new_filelist    = []

    for filename in filelist:
        ext=filename[-3:]

        if os.path.isfile(filename):
            if is_rast(filename):
                new_filelist.append(filename)

    return(new_filelist)


def project_resamp(filelist, reference_file, outdir = False,
                   resampling_type = False, cell_size = False):

    """
    Wrapper for multiple arcpy projecting functions. Projects to reference file
    
     Inputs a filelist and a reference file, then projects all rasters or feature classes
     in the filelist to match the projection of the reference file. Writes new files with a
     "_p" appended to the end of the input filenames. This also will perform resampling.

     Inputs:
       filelist            list of files to be projected
       outdir              optional desired output directory. If none is specified, output files
                           will be named with '_p' as a suffix.
       reference_file      Either a file with the desired projection, or a .prj file.
       resampling type     exactly as the input for arcmaps project_Raster_management function
       cell_size           exactly as the input for arcmaps project_Raster_management function

     Output:
       Spatial reference   spatial referencing information for further checking.
    """

    # sanitize inputs
    core.exists(reference_file)
           
    rasterlist  = enf_rastlist(filelist)
    featurelist = core.enf_featlist(filelist)
    cleanlist   = rasterlist + featurelist

    # ensure output directoryexists
    if not os.path.exists(outdir):
        os.makedirs(outdir)
        
    # grab data about the spatial reference of the reference file. (prj or otherwise)
    if reference_file[-3:]=='prj':
        Spatial_Reference = arcpy.SpatialReference(Spatial_Reference)
    else:
        Spatial_Reference = arcpy.Describe(reference_file).spatialReference
        
    # determine wether coordinate system is projected or geographic and print info
    if Spatial_Reference.type == 'Projected':
        print('Found {0} projected coord system'.format(Spatial_Reference.PCSName))
    else:
        print('Found {0} geographic coord system'.format(Spatial_Reference.GCSName))


    for filename in cleanlist:
        
        # create the output filename
        outname = core.create_outname(outdir, filename, 'p')

        # use ProjectRaster_management for rast files
        if is_rast(filename):
            if resampling_type:
                
                arcpy.ProjectRaster_management(
                    filename, outname, Spatial_Reference,resampling_type, cell_size)
                print('Wrote projected and resampled file to {0}'.format(outname))
                
            else:
                arcpy.ProjectRaster_management(filename, outname, Spatial_Reference)
                print('Wrote projected file to {0}'.format(outname))
                
        # otherwise, use Project_management for featureclasses and featurelayers
        else:
            arcpy.Project_management(filename,outname,Spatial_Reference)
            print('Wrote projected file to {0}'.format(outname))

    print("finished projecting!")
    return(Spatial_Reference)

    
def show_stats(numpy_rast, fig , im, title = False):
    """
    Function to show stats, updates a figure that already exists
    """

    if title:
        fig.suptitle(title, fontsize = 20)
        
    im.set_data(numpy_rast)
    fig.canvas.draw()
    return


def make_fig(numpy_rast, title = False):
    """function to set up an updating figure"""

    fig, ax = plt.subplots()
    fig.show()

    im = ax.imshow(numpy_rast)

    if title:
        fig.suptitle(title, fontsize = 20)
        
    im.set_data(numpy_rast)
    fig.canvas.draw()
    return fig, im


def close_fig(fig, im):
    """closes an active figure"""

    plt.close(fig)
    return

