'''

Apply the segmentation masks over the images

'''


from HelperFunctions.Utilities import dirMaker, nameFromPath, getMatchingList
import cv2
import numpy as np
from glob import glob
import matplotlib.pyplot as plt

src = '/Volumes/USB/H653A_11.3/3/'

imgsrc = src + "SegmentationManual/"
model = "ResNet101"
model = "VGG16"
segsrc = src + "Segmentations" + model + "/"
imgDest = src + "SegmentationsEvals" + model + "/"

masks = sorted(glob(segsrc + "*.png"))
imgs = sorted(glob(imgsrc + "*anno*.png"))

dirMaker(imgDest)

maskToUse = getMatchingList(imgs, masks)

for n, (m, i) in enumerate(zip(maskToUse, imgs)):

    if m is None:
        continue

    name = nameFromPath(i, 3)

    print(name + " Processing")

    img = cv2.imread(i)
    mask = cv2.imread(m)

    xi, yi, _ = img.shape
    xm, ym, _ = mask.shape

    xr, yr = tuple(np.round((xi / xm) * np.array([xm, ym])).astype(int))
    imgStored = []
    for ni, i in enumerate(np.unique(mask)):

        plate = np.zeros(mask.shape).astype(np.uint8)
        if model == "ResNet101":
            nx = 4
            ny = 5
            plate[nx:, ny:, :] = mask[:-nx, :-ny, :]
        elif model == "VGG16":
            nx = 4
            ny = 2
            plate[:-nx, ny:, :] = mask[nx:, :-ny, :]
            
    
        # get the mask of only the particular tissue type
        maskFull = cv2.resize(((plate==i)*0.75 + 0.25), tuple([yr, xr]))
        xf, yf, _ = maskFull.shape

        if i == 0:
            maskCover = np.ones([xi, yi, 3]); maskCover[:xr, :yr, :] = maskFull
        else:
            maskCover = np.zeros([xi, yi, 3]); maskCover[:xr, :yr, :] = maskFull
            
        # make the background a value of 1 now
        img[img==[0, 0, 0]] = 50
        # mask the image and where the background is included, set value to 1
        imgMasked = (img*maskCover).astype(np.uint8)

        imgStored.append(imgMasked)

        cv2.imwrite(imgDest + str(name) + "_" + str(ni) + ".png", imgMasked)# np.hstack(imgStored))