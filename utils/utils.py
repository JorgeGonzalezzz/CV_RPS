import numpy as np
import cv2
import glob
import matplotlib.pyplot as plt

def load_images(path):
    return [cv2.imread(image) for image in path]

def show_images_h(hands):
    n = len(hands)
    if n == 0:
        print("No images to display.")
        return

    plt.figure(figsize=(4 * n, 4))

    for i, img in enumerate(hands):
        plt.subplot(1, n, i + 1)
        # Convert BGR (OpenCV) to RGB (matplotlib)
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        plt.imshow(img_rgb)
        plt.axis("off")

    plt.show()


def hsv_images(images):
    return [cv2.cvtColor(img, cv2.COLOR_BGR2HSV) for img in images]

def get_mask(images, minmask, topmask):
    hsvs = hsv_images(images)
    masks = [cv2.inRange(img, minmask, topmask) for img in hsvs]
    return [cv2.bitwise_and(img, img, mask=mask) for img, mask in zip(images, masks)]


def get_mask_or(images, mask1, mask2):
    lower1, upper1 = mask1
    lower2, upper2 = mask2

    masked_images = []

    for img in images:
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

        m1 = cv2.inRange(hsv, lower1, upper1)
        m2 = cv2.inRange(hsv, lower2, upper2)

        mask_or = cv2.bitwise_or(m1, m2)
        masked = cv2.bitwise_and(img, img, mask=mask_or)

        masked_images.append(masked)

    return masked_images



def nothing(x):
    pass

def get_hsv_color_ranges(image: np.array):

    # Create a window
    cv2.namedWindow('image')

    # Create trackbars for color change
    cv2.createTrackbar('HMin', 'image', 0, 255, nothing)
    cv2.createTrackbar('SMin', 'image', 0, 255, nothing)
    cv2.createTrackbar('VMin', 'image', 0, 255, nothing)
    cv2.createTrackbar('HMax', 'image', 0, 255, nothing)
    cv2.createTrackbar('SMax', 'image', 0, 255, nothing)
    cv2.createTrackbar('VMax', 'image', 0, 255, nothing)

    # Set default value for MAX HSV trackbars.
    cv2.setTrackbarPos('HMax', 'image', 255)
    cv2.setTrackbarPos('SMax', 'image', 255)
    cv2.setTrackbarPos('VMax', 'image', 255)

    # Initialize to check if HSV min/max value changes
    hMin = sMin = vMin = hMax = sMax = vMax = 0
    phMin = psMin = pvMin = phMax = psMax = pvMax = 0

    output = image
    wait_time = 33

    while(1):

        if cv2.getWindowProperty('image', cv2.WND_PROP_VISIBLE) < 1:
            break
        # Get current positions of all trackbars
        hMin = cv2.getTrackbarPos('HMin','image')
        sMin = cv2.getTrackbarPos('SMin','image')
        vMin = cv2.getTrackbarPos('VMin','image')

        hMax = cv2.getTrackbarPos('HMax','image')
        sMax = cv2.getTrackbarPos('SMax','image')
        vMax = cv2.getTrackbarPos('VMax','image')

        # Set minimum and max HSV values to display
        lower = np.array([hMin, sMin, vMin])
        upper = np.array([hMax, sMax, vMax])

        # Create HSV Image and threshold into a range.
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, lower, upper)
        output = cv2.bitwise_and(image,image, mask= mask)

        # Print if there is a change in HSV value
        if( (phMin != hMin) | (psMin != sMin) | (pvMin != vMin) | (phMax != hMax) | (psMax != sMax) | (pvMax != vMax) ):
            print("(hMin = %d , sMin = %d, vMin = %d), (hMax = %d , sMax = %d, vMax = %d)" % (hMin , sMin , vMin, hMax, sMax , vMax))
            phMin = hMin
            psMin = sMin
            pvMin = vMin
            phMax = hMax
            psMax = sMax
            pvMax = vMax

        # Display output image
        cv2.imshow('image',output)
        # cv2.resizeWindow("image", 500,300)

        # Wait longer to prevent freeze for videos.
        if cv2.waitKey(wait_time) & 0xFF == ord('q'):
            break

    cv2.destroyAllWindows()
