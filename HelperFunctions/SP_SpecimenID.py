'''
This function automatically creates a mask around the target specimen and seperates multiple 
samples into seperate images.
'''

import numpy as np
import cv2
import matplotlib.pyplot as plt
import os 
from glob import glob
from multiprocessing import Pool
import multiprocessing
from itertools import repeat
if __name__ != "HelperFunctions.SP_SpecimenID":
    from Utilities import *
    from plottingFunctions import colourDistributionHistos
else:
    from HelperFunctions.Utilities import *
    from HelperFunctions.plottingFunctions import colourDistributionHistos

'''
TODO: explanation of what happens here.....

-  Investigate if this now works for a single sift operator applied over the 
entire image, rather than segmenting the image into grids

'''

# NOTE can probably depreciate specID and make sectionSelecter the main function
def specID(dataHome, size, cpuNo = False, imgref = 'refimg.png', plot = True):

    # get the size specific source of information
    datasrc = dataHome + str(size) + "/"

    # get the reference image path
    if imgref is not None:
        refimgPath = getSampleName(dataHome, imgref)
        imgref = cv2.imread(refimgPath)

    # gets the images for processing
    sectionSelecter(datasrc, cpuNo, imgref, plot)


def sectionSelecter(datasrc, cpuNo = False, imgref = None, plot = False):

    '''
    This function creates a mask which is trying to selectively surround
    ONLY the target tissue and normalises the image colours

        Inputs:

    (spec), the specific sample being processed\n
    (datasrc), the location of the jpeg images (as extracted)\n
    (cpuNo), number of cores to use for parallelisations\n
    (refimg), the reference image to use for colour normalisations. If set to None
    will not perform this\n

        Outputs:\n

    (), create the down-sampled and full scale tif images with their respecitve 
    samples extracted and with their colours normalised against a reference image 
    '''
    
    imgsrc = datasrc + "images/"
    imgbigsrc = datasrc + "tifFiles/"

    # create the directory where the masked files will be created
    imgMasked = datasrc + "maskedSamples/"
    imgMasks = imgMasked + "masks/"
    imgPlots = imgMasked + "plot/"
    dirMaker(imgMasks)
    dirMaker(imgPlots)
    
    # get all the small images 
    imgsmall = sorted(glob(imgsrc + "*.png"))

    
    print("\n   #--- SEGMENT OUT EACH IMAGE AND CREATE MASKS ---#")
    # serialised
    if cpuNo == 1:
        for idir in imgsmall:    
            maskMaker(idir, imgMasks, imgPlots, plot)

    else:
        # parallelise with n cores
        with Pool(processes=cpuNo) as pool:
            pool.starmap(maskMaker, zip(imgsmall, repeat(imgMasks), repeat(imgPlots), repeat(plot)))
    
    print("\n   #--- APPLY MASKS ---#")
    
    # get the directories of the new masks
    masks = sorted(glob(imgMasks + "*.pbm"))

    # use the first image as the reference for colour normalisation
    # NOTE use the small image as it is faster but pretty much the 
    # same results

    # imgref = None
    # serialised
    if cpuNo == 1:
        for m in masks:
            imgStandardiser(imgMasked, m, imgsrc, imgref)

    else:
        # parallelise with n cores
        with Pool(processes=cpuNo) as pool:
            pool.starmap(imgStandardiser, zip(repeat(imgMasked), masks, repeat(imgsrc), repeat(imgref)))

    print('Info Saved')

def maskMaker(idir, imgMasked = None, imgplot = False, plot = False):     

    # this function loads the desired image extracts the target sample:
    # Inputs:   (img), the image to be processed
    #           (imgplot), boolean whether to show key processing outputs, defaults false
    # Outputs:  (im), mask of the image  

    #     figure.max_open_warning --> fix this to not get plt warnings

    # use numpy to allow for parallelisation
    try:
        imgO = np.round(np.mean(cv2.imread(idir), 2)).astype(np.uint8)
    except:
        print("FAILED: " + idir)
        return

    name = nameFromPath(idir)

    print(name + " masking")
    rows, cols = imgO.shape

    img = imgO.copy()

    # ----------- specimen specific cropping -----------
    
    if name.find("H653") >= 0:
        '''
        H653 has bands from the plate which the specimen is stored on which causes a lot of 
        disruption to the img and compared to the amount of tissue in these bands, is more of an
        issue 
        '''

        img[:int(cols * 0.08), :] = np.median(img)
        img[-int(cols * 0.05):, :] = np.median(img)

    if name.find("H710B") >= 0:
        # remove some of the bottom row
        img[-int(cols*0.05):, :] = np.median(img)
    
    if name.find("H710C") >= 0:
        # remove a little bit of the left hand side of the image 
        img[:, -int(rows*0.05):] = np.median(img)

    if name.find("H673A") >= 0:
        # remove some of the bottome
        img[-int(cols * 0.08):, :] = np.median(img)

    if name.find("H671A") >= 0:
        # remove some of the top and bottom
        img[:int(cols*0.05), :] = np.median(img)
        img[-int(cols*0.05):, :] = np.median(img)

    if name.find("H750") >= 0:

        # remove some of the top and bottom
        img[:int(cols*0.07), :] = np.median(img)
        img[-int(cols*0.1):, :] = np.median(img)

    # ----------- background remove filter -----------

    # find the colour between the two peak value distributions 
    # this is threshold between the background and the foreground
    lBin = 20
    hBin = len(np.unique(img))
    rBin = hBin/lBin
    histVals, histBins = np.histogram(img, lBin)

    # the background is the maximum pixel value
    backPos = np.argmax(histVals)

    # the end of the foreground is at the inflection point of the pixel count
    diffback = np.diff(histVals[:backPos])
    try:
        forePos = np.where(np.diff(diffback) < 0)[0][-1] + 1
    except:
        forePos = backPos - 2

    # find the local minima between the peaks on a higher resolution histogram profile
    histValsF, histBinsF = np.histogram(img, hBin)
    backVal = int(np.round((forePos + 1) * rBin + np.argmin(histValsF[int(np.round(forePos + 1) * rBin):int(np.round(backPos * rBin))])))
    background = histBinsF[backVal]

    # accentuate the colour
    im_accentuate = img.copy()
    b = background
    im_binary = (((im_accentuate - b) < 0)*1).astype(np.uint8)

    # ----------- smoothing -----------
    # create kernel
    kernelb = np.ones([5, 5])
    kernelb /= np.sum(kernelb)

    # apply 
    img_smooth = cv2.filter2D(im_accentuate,-1,kernelb)
    img_smooth = cv2.erode(img_smooth, (3, 3), iterations=1)

    # ----------- adaptative binarising -----------

    # threshold to form a binary mask
    v = int((np.median(img_smooth) + np.mean(img_smooth))/2)
    im_binary = (((img_smooth<v) * 255).astype(np.uint8)/255).astype(np.uint8) #; im = ((im<=200) * 0).astype(np.uint8)  
    im_binary = cv2.dilate(im_binary, (5, 5), iterations=20)      # build edges back up
    
    # ----------- single feature ID -----------
    
    # create three points to use depending on what works for the flood fill. One 
    # in the centre and then two in the upper and lower quater along the vertical line
    points = []
    try:
        for x in np.arange(0.25, 1, 0.25):
            for y in np.arange(0.25, 1, 0.25):
                binPos = np.where(im_binary==1)
                pointV = binPos[0][np.argsort(binPos[0])[int(len(binPos[0])*y)]]
                vPos = np.where(binPos[0] == pointV)
                pointH = binPos[1][vPos[0]][np.argsort(binPos[1][vPos[0]])[int(len(vPos[0])*x)]]
                points.append(tuple([int(pointH), int(pointV)]))   # centre point
    except:
        print("     " + name + " FAILED")
        return

    # flood fill all the points found and if it is significant (ie more than a 
    # threshold % of the image is filled) keep if
    im_id = im_binary * 0
    for point in points:
        im_search = (cv2.floodFill(im_binary.copy(), None, point, 255)[1]/255).astype(np.uint8)
        if np.sum(im_search) > im_search.size * 0.05:
            im_id += im_search

    # ensure that im_id is only a mask of 0 and 1
    im_id = ((im_id>0)*1).astype(np.uint8)

    # perform an errosion on a flipped version of the image
    # what happens is that all the erosion/dilation operations work from the top down
    # so it causes an accumulation of "fat" at the bottom of the image. this removes it
    im_id = cv2.rotate(cv2.dilate(cv2.rotate(im_id, cv2.ROTATE_180), (5, 5), iterations = 10), cv2.ROTATE_180)

    # save the mask as a .pbm file
    cv2.imwrite(imgMasked + name + ".pbm", im_id)
    print("     " + name + " Masked")
    # plot the key steps of processing
    if plot:
        # create sub plotting capabilities
        # fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2)
        
        f, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2)

        # plot the target tissue identified 
        ax1.imshow(255-im_accentuate, cmap = 'gray')
        ax1.axis("off")
        ax1.title.set_text("accentuated colour Mask")

        # plot the tissue to be extracted and the location of the flood fill operations
        im_binary3d = (np.ones([im_binary.shape[0], im_binary.shape[1], 3]) * np.expand_dims(im_binary * 255, -1)).astype(np.uint8)
        for point in points:
            cv2.circle(im_binary3d, tuple(point), 100, (255, 0, 0), 20)
        ax2.imshow(im_binary3d)
        ax2.axis("off")
        ax2.title.set_text("centreFind Mask")

        # plot the extracted tissue areas
        ax3.imshow(im_id, cmap = 'gray')
        ax3.axis("off")
        ax3.title.set_text("identified section")

        # plot the extracted tissue in each slide
        imgMod = imgO * im_id
        extract = bounder(im_id)
        for n in extract:
            x, y = extract[n]
            for i in range(2):
                cv2.line(imgMod, (x[i], y[i]), (x[1], y[0]), (255, 0, 0), 10)
                cv2.line(imgMod, (x[i], y[i]), (x[0], y[1]), (255, 0, 0), 10)
        ax4.imshow(imgMod, cmap = "gray") 
        ax4.axis("off")
        ax4.title.set_text("masked image")
        f.tight_layout(pad = 1)
        plt.savefig(imgplot + name + ".jpg")
        plt.clf()

def imgStandardiser(destPath, maskpath, imgsrc, imgRef, ratio = 1):

    # this applies the mask created to the lower resolution and full 
    # resolution images and creates information needed for the alignment
    # an area of the largest possible dimension of all the images
    # Inputs:   (maskPath), path of the sample mask
    #           (imgbigpath), path of the tif image of the samples
    #           (imgsmallpath), path of the reduced sized image
    #           (imgref), reference image for colour normalisation
    #           (ratio), scale of the mask to the image it is being applied to
    # Outputs:  (), saves image at destination with standard size and mask if inputted


    # get info to place all the images into a standard size to process (if there
    # is a mask)

    name = nameFromPath(maskpath)
    print(name + " modifying")
    dirMaker(destPath)

    # get the imgpath. if it fails just break
    try:    
        imgpath = glob(imgsrc + name + "*.*")[0]
    except: 
        print("     FAILED image: " + imgsrc + name)
        return
   # read in the image, either as a tif or non-tif image
    if imgpath.split(".")[-1] == "tif":
        tif = True
        img = tifi.imread(imgpath)
    else:
        tif = False
        img = cv2.imread(imgpath)

    # read in the raw mask
    try:
        mask = (cv2.imread(maskpath)/255).astype(np.uint8)
    except:
        print("     FAILED mask: " + maskpath)
        return

    # get the bounding positional information
    extract = bounder(mask[:, :, 0])

    id = 0
    for n in extract:

        if mask is None or img is None:
            print("\n\n!!! " + name + " failed!!!\n\n")
            break

        # get the co-ordinates
        x, y = extract[n]

        # extract only the mask containing the sample
        maskE = mask[y[0]:y[1], x[0]:x[1], :]

        # if each of the mask section is less than 20% of the entire mask 
        # area, it probably isn't a sample and is not useful
        if maskE.size < mask.size * 0.2 / len(extract) or np.sum(maskE) == 0:
            continue

        # create a a name
        newid = name + "_" + str(id)

        # adjust for the original size image
        xb, yb = (np.array(extract[n]) *  ratio).astype(int)
        imgsect = img[:, :, :][yb[0]:yb[1], xb[0]:xb[1], :].copy()

        # expand the dims so that it can multiply the original image
        maskS = cv2.resize(maskE, (imgsect.shape[1], imgsect.shape[0])).astype(np.uint8)

        # apply the mask to the images 
        imgsect *= maskS

        # normalise the colours
        if imgRef is not None:
            imgsect = imgNormColour(imgsect, imgRef, tif)#, imgbigsect)

        if False:
            colourDistributionHistos(img[y[0]:y[1], x[0]:x[1], :]*maskS, imgRef, imgsect)

        # write the new images
        if tif:
            tifi.imwrite(destPath + newid + ".tif", imgsect)
        else:
            cv2.imwrite(destPath + newid + ".png", imgsect)

        id += 1

        print("     " + newid + " made")

def imgNormColour(img, imgref, tif):

    '''
    Normalises all the colour channels of an image

        Inputs:\n

    (img), image to modify
    (imgref), image as array which has the colour properties to match
    (tif), boolean. If true then convert the reference image channels as necessary

        Outputs:\n  

    (), over-writes the old images wit the new ones
    '''

    if tif:
        imgref = cv2.cvtColor(imgref, cv2.COLOR_BGR2RGB)

    imgMod = hist_match(img, imgref)   

    return(imgMod)
        
if __name__ == "__main__":

    multiprocessing.set_start_method('spawn')

    dataSource = '/Volumes/USB/Testing1/'
    dataSource = '/Volumes/USB/IndividualImages/'
    dataSource = '/Volumes/USB/H671B_18.5/'
    dataSource = '/Volumes/Storage/H653A_11.3/'
    dataSource = '/Volumes/USB/H1029A_8.4/'
    dataSource = '/Volumes/USB/Test/'
    dataSource = '/Volumes/USB/H750A_7.0/'
    dataSource = '/Volumes/USB/H671A_18.5/'
    dataSource = '/Volumes/USB/H673A_7.6/'
    dataSource = '/Volumes/USB/H710C_6.1/'
    dataSource = '/Volumes/USB/H710B_6.1/'
    dataSource = '/Volumes/USB/H653A_11.3/'

    size = 3
    cpuNo = 1
        
    specID(dataSource, size, cpuNo)