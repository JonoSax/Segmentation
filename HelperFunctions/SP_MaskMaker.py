'''

this creates a mask from the annotations which indicates the 
regions which are the annotated tissue

'''

import os
import numpy as np
from glob import glob
import matplotlib.pyplot as plt
from skimage.segmentation import flood_fill
from multiprocessing import Pool
from itertools import repeat
if __name__ != "HelperFunctions.SP_MaskMaker":
    from Utilities import *
else:
    from HelperFunctions.Utilities import *

'''

TODO 
    - Seperate into two functions the mask building and target tissue identification

'''


# magnification levels of the tif files available
tifLevels = [20, 10, 5, 2.5, 1.25, 0.625, 0.3125, 0.15625]

def maskMaker(dataTrain, size, cpuNo = 1):

    # this is the function called by main. Organises the inputs for findFeats
    specimens = sorted(nameFromPath(glob(dataTrain + "*.ndpa")))

    '''
    for s in specimens:
        maskCreator(dataTrain, s, size)
    '''

    # parallelise work
    if cpuNo > 1:
        with Pool(processes=cpuNo) as pool:
            pool.starmap(maskCreator, zip(repeat(dataTrain), specimens, repeat(size)))

    else:
        for s in specimens:
            maskCreator(dataTrain, s, size)

def maskCreator(dataTrain, segmentName, size = 0):

    # This function takes the manual annotations and turns them into a dense matrix which 
    # has identified all the pixel which the annotations encompass at the user chosen scale
    # Inputs:   (size), the user chosen scale which refers to the zoom level of the tif file extracted
    #               by default it is create a mask on the highest resolution
    #           (specimenAnnotations), list of the annotations as loaded by annotationsReaders
    # Outputs:  (), txt files which contains all pixel locations for the specified resolution
    #            of the tif file 

    specimenPosDir = sorted(glob(dataTrain + "posFiles/" + segmentName + "*.pos"))
    tifDir = sorted(glob(dataTrain + str(size) + "/tifFiles/" + segmentName + "*.tif"))
    
    tifSource = dataTrain + str(size) + "/tifFiles/"
    maskDir = dataTrain + str(size) + "/maskFiles/" 
    dirMaker(maskDir)

    scale = size / max(tifLevels)
    
    for pos, tif in zip(specimenPosDir, tifDir):

        name = nameFromPath(pos)

        # open the manual annotations file
        annoSpec, argsDict = txtToList(pos)
        
        # find the encomappsed areas of each annotations
        denseAnnotations = maskFinder(name, annoSpec, 1)
        
        # of the identified areas, find the overlapping areas
        targetTissue = featureFinder(name, denseAnnotations)

        # maskCover(tif, maskDir + name + '_masked', targetTissue) 

        # NOTE this makes the identified vessels during the ACTUAL processing inverted colour
        maskCover(tif, maskDir + name, targetTissue, scale, small=False) 

        # save the mask as a txt file of all the pixel co-ordinates of the target tissue
        # listToTxt(targetTissue, maskDir + name + "_" + str(size) + ".mask")
    
def maskFinder(name, annoSpec, scale = 1):

    # This function takes the manual annotations and turns them into a mask which 
    # encompasses the inner area of the circled vessels
    # Inputs:   (annoSpec), the annotations for a single specimen
    #           (scale), the scaling factor to apply between the raw data and the chosen 
    #               tif size file to analyse
    # Outputs:  (denseAnnotations), a list containing the global co-ordinate position of ONLY
    #               the true values of the mask

    # --- perform mask building per annotation
    denseAnnotations = list()

    for n in range(len(annoSpec)):

        if n%20 == 0:
            print("Annotation " + str(n) + "/" + str(len(annoSpec)) + " of " + name)

        # process per annotation
        annotation = annoSpec[n]

        # scale the annotation
        annotationScaled = annotation * scale

        # shift the individual annotation to a (0, 0) origin and scale to the actual image size
        xminO = int(annotationScaled[:, 0].min())
        yminO = int(annotationScaled[:, 1].min())
        annotationU, posU = np.unique((annotationScaled - [xminO, yminO]).astype(int), axis = 0, return_index = True)           

        # get the properties of the new scaled grid
        xmax = int(annotationScaled[:, 0].max())
        ymax = int(annotationScaled[:, 1].max())
        xmin = int(annotationScaled[:, 0].min())
        ymin = int(annotationScaled[:, 1].min())

        # after np.unique the entries are ordered by value which breaks the interpolation step as it works on the 
        # assumption of sequential points. So re-order the now downsampled hand annotations
        posM, annotationM = zip(*sorted(zip(posU, annotationU)))
        annotationM = np.array(annotationM)

        # scaled grid
        gridX = xmax-xmin+3
        gridY = ymax-ymin+3
        grid = np.zeros([gridX, gridY])     # NOTE: added 3 so that the entire bounds of the co-ordinates are stored... 

        # --- Interpolate between each annotated point creating a continuous border of the annotation
        x_p, y_p = annotationM[-1]      # initialise with the last point for continuity 
        for x, y in annotationM:

            # number of points needed for a continuous border
            num = int(sum(np.abs(np.subtract((x, y),(x_p, y_p)))))

            # generating the x and y region points
            x_r = np.linspace(x, x_p, num+1)
            y_r = np.linspace(y, y_p, num+1)

            # perform a "blurring" operation to ensure the outline of the mask is solid
            extrapolated01 = np.stack([np.clip(x_r-1, 0, gridX), np.clip(y_r, 0, gridY)], axis = 1)
            extrapolated21 = np.stack([np.clip(x_r+1, 0, gridX), np.clip(y_r, 0, gridY)], axis = 1)
            extrapolated11 = np.stack([np.clip(x_r, 0, gridX), np.clip(y_r, 0, gridY)], axis = 1)
            extrapolated10 = np.stack([np.clip(x_r, 0, gridX), np.clip(y_r-1, 0, gridY)], axis = 1)
            extrapolated12 = np.stack([np.clip(x_r, 0, gridX), np.clip(y_r+1, 0, gridY)], axis = 1)

            extrapolated = np.concatenate([extrapolated21,
                                            extrapolated01,
                                            extrapolated11,
                                            extrapolated10,
                                            extrapolated12,]).astype(int)

            # set these points as true
            for x_e, y_e in extrapolated:
                grid[x_e, y_e] = 1
            
            # save previous point to i
            x_p, y_p = x, y
            
            #print("x_r: " + str(x_r))
            # print("y_r: " + str(y_r) + "\n")
            # plt.imshow(grid); plt.show()

        # find a point inside the feature to perform a flood fill operation
        roi = roiFinder(grid)

        # floodfill in the entirety of this encompassed area
        try:
            gridN = flood_fill(grid, roi, 1)
        except:
            gridN = grid
            print("Flood not performed on annotation " + str(n) + " from " + name)

        # --- save the mask identified in a dense form and re-position into the SCALED global space
        denseGrid = np.stack(np.where(gridN == 1), axis = 1) + [xmin, ymin]
        # denseMatrixViewer(denseGrid)
        # plt.imshow(grid); plt.show()
        denseAnnotations.append(denseGrid)
    
    # return a list which contains all the true pixel positions of the circled areas
    return(denseAnnotations)

def featureFinder(name, denseAnnotations):

    # This function takes the dense list of mask value positions from maskFinder and 
    # identifies which pair of these masks overlap and then identifies the roi target
    # tissue between the areas
    # Inputs:   (annoSpec), the dense list of co-ords for the mask from maskFinder
    # Outputs:  (targetTissue), dense list of co-ords for ONLY the areas between the 
    #               annotated masks
    
    # perform a boundary search to investigate which masks are within which sections
    annoID = np.arange(len(denseAnnotations))
    noAnnos = len(annoID)

    targetTissue = list()

    # --- identify the target tissue between paired annotations
    while len(annoID) > 0:

        s = annoID[0]
        # print("\nAnnotation " + str(s) + "/" + str(noAnnos))
        annoID = np.delete(annoID, np.where(annoID == s)[0][0])      # as you find matches remove from array search
        
        # annotation to perform search
        search = denseAnnotations[s]
        sXmax = search[:, 0].max()
        sXmin = search[:, 0].min()
        sYmax = search[:, 1].max()
        sYmin = search[:, 1].min()
            

        # need to check if search is either the inside or outside mask
        '''
        b, sb = denseMatrixViewer(search, plot = False, gray = True)
        bx, by = b.shape

        # end point
        eb = np.array(sb) + (bx**2 + by**2)**0.5
        found = False
        '''
        found = False
        matchedTissue = []
        for m in annoID:
            
            match = denseAnnotations[m]

            mXmax = match[:, 0].max()
            mXmin = match[:, 0].min()
            mYmax = match[:, 1].max()
            mYmin = match[:, 1].min()

            # logic operators to check if there is an encompassed area
            mInsideBool = (mXmax <= sXmax) & (mYmax <= sYmax) & (mXmin >= sXmin) & (mYmin >= sYmin)
            mOutsideBool = (mXmax >= sXmax) & (mYmax >= sYmax) & (mXmin <= sXmin) & (mYmin <= sYmin)

            # check if match is inside the search
            if mInsideBool or mOutsideBool:
                annoID = np.delete(annoID, np.where(annoID == m)[0][0])
                matchedTissue.append(match)                
                found = True
            
        if found:
            annotatedROI = coordMatch(search, np.vstack(matchedTissue))
            targetTissue.append(annotatedROI)
        else:
            targetTissue.append(search)
            print("anno " + str(s) + " not matched from " + name)

        if len(targetTissue)%20 == 0:
            print("Match " + str(len(targetTissue)))

        # view the roi
        # denseMatrixViewer([annotatedROI])

    # NOTE, can probably put the maskCover function here....

    return(targetTissue)

def maskCover(dir, dirTarget, masks, scale, small = True):

    # This function adds add the mask outline to the image
    # Inputs:   (dir), the SPECIFIC name of the tif image the mask was made on
    #           (dirTarget), the location to save the image
    #           (masks), list of each array of co-ordinates for all the annotations
    #           (small), boolean whether to add the mask to a smaller file version (ie jpeg) or to a full version (ie tif)
    # Outputs:  (), re-saves the image with mask of the vessels drawn over it

    imgR = tifi.imread(dir)
    hO, wO, _ = imgR.shape

    '''
    # if the image is more than 70 megapixels downsample 
    if (hO * wO >= 100 * 10 ** 6) & small:
        size = 2000
        aspectRatio = hO/wO
        imgR = cv2.resize(imgR, (size, int(size*aspectRatio)))
    '''

    h, w, c = imgR.shape

    # scale the mask to the downsampled image
    # scale = h/hO
    for n, mask in enumerate(masks):
        if n%20 == 0: 
            print("Match drawn " + str(n) + "/" + str(len(masks)))
        maskN = np.unique((mask * scale).astype(int), axis = 0)
        imgR[maskN[:, 1], maskN[:, 0]] = [0, 255, 0]
        # cv2.putText(imgR, str(n), tuple(maskN[0, :]), cv2.FONT_HERSHEY_SIMPLEX, 1, [0, 0, 0], 4)

    tifi.imwrite(dirTarget + ".tif", imgR)

    # cv2.imwrite(newImg, imgR, [cv2.IMWRITE_JPEG_QUALITY, 80])
    # cv2.imshow('kernel = ' + str(kernel), imgR); cv2.waitKey(0)

def roiFinder(grid):

    for x in range(grid.shape[0]):
        edges = np.zeros([2, 2])
        startFound = False  

        # for every y point
        for y in range(1, grid.shape[1]-3):

            # check if there was a raising edge point on this row with at least 4 spaces around it
            if (grid[x, y+1]).all() == 0 & (grid[x, y] == 1):
                edges[0, :] = [x, y]
                startFound = True
                
            # check if there is a falling edge point on this row
            elif (grid[x, y-1] == 0) & (grid[x, y] == 1) & startFound:
                edges[1, :] = [x, y]
                
                # find the middle of the edge --> assumed this will be a pixel within the roi
                roi0 = tuple(np.mean(edges, axis = 0).astype(int))
                
                # AT THIS POINT WE HAVE POTENTIALLY FOUND AN EDGE. HOWEVER DUE
                # TO HUMAN BS WHEN DRAWING THE ANNOTATIONS WE NEED TO CHECK OVER 
                # THIS EDGE WITH ANOTHER METHOD --> CONFIRM THE EXISTENCE OF THE 
                # EDGE IN THE VERTICAL PLANE AS WELL
                # perform a vertical search to confirm roi
                startFound = False
                for x in range(1, grid.shape[0]-1):
                    yroi0 = roi0[1]
                    # check if there is a raising edge point on this column
                    if (grid[x+1, yroi0] == 0).all() & (grid[x, yroi0] == 1):
                        edges[0, :] = [x, yroi0]
                        startFound = True
                        
                    # check if there is a falling edge point on this column
                    elif (grid[x-1, yroi0] == 0) & (grid[x, yroi0] == 1) & startFound:
                        edges[1, :] = [x, yroi0]
                        
                        # find the middle of the edge --> assumed this will be a pixel within the roi
                        roi = tuple(np.mean(edges, axis = 0).astype(int))
                        return(roi)

def coordMatch(array1, array2):

    # This function removes the values of the smaller array from the larger array to identify the roi.
    # Inputs:   (largerArray), numpy.array which contains vector values. MUST be the larger dimension 
    #           (smallerArray), numpy.array which contains vector values. MUST be the smaller dimension 
    # Outputs:  (roi), essentailly the areas which are unique to the larger array

    # get each array entry repeated once and count its occurence
    uniq, count = np.unique(np.concatenate([array1, array2]), return_counts=True, axis = 0)

    # only pass through the entires which occur once --> removes the points of overlap
    roi = uniq[np.where(count == 1)]

    return(roi)

if __name__ == "__main__":

    dataTrain = '/Volumes/USB/H653A_11.3/'
    size = 2.5
    cpuNo = 6

    maskMaker(dataTrain, size, cpuNo)
