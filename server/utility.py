import tensorflow as tf
from tensorflow import keras
import json
import cv2 as cv
import numpy as np
import re


__class_name_to_number = {}
__class_number_to_name = {}

__model = None

# load artifacts
def load_saved_artifacts():
    print("Loading saved artifacts...start")

    global __class_name_to_number
    global __class_number_to_name

    with open("./artifacts/class_dictionary.json", "r") as f:
        __class_name_to_number = json.load(f)
        __class_number_to_name = {v:k for k,v in __class_name_to_number.items()}

    global __model

    if __model is None:
         __model = tf.keras.models.load_model('./artifacts/CNN.model')
    print("Loading saved artifacts...done")

# find contours
def find_contours(img):

    imgray = cv.cvtColor(img, cv.COLOR_BGR2GRAY)
    ret, thresh = cv.threshold(imgray, 100, 255, 0)
    return cv.findContours(
        thresh, cv.RETR_TREE, cv.CHAIN_APPROX_SIMPLE)

# checks wether 2 bounding boxes overlap over given axes 
def overlapping_axes(coord1, delta1, coord2, delta2):
    
    if coord1 <= coord2 + delta2 and coord1 >= coord2:
        return True
    if coord1 + delta1 <= coord2 + delta2 and coord1 + delta1 >= coord2:
        return True
    if coord2 <= coord1 + delta1 and coord2 >= coord1:
        return True
    if coord2 + delta2 <= coord1 + delta1 and coord2 + delta2 >= coord1:
        return True

    return False

# finds all contours and chooses ones that best contour given characters
def remove_overlapping_bounding_boxes(boundingRects):

    # If 2 bounding boxes are overlapping, take the bigger one
    for i in range(len(boundingRects)):
        if boundingRects[i] is None:
            continue
        for j in range(i + 1, len(boundingRects)):
            if boundingRects[j] is None:
                continue
            x1, y1, width1, height1 = boundingRects[i]
            x2, y2, width2, height2 = boundingRects[j]

            if overlapping_axes(x1, width1, x2, width2) and overlapping_axes(y1, height1, y2, height2):
                if width1 * height1 > width2 * height2:
                    boundingRects[j] = None
                else:
                    boundingRects[i] = None
                    break

    return [bounding for bounding in boundingRects if bounding is not None]

# crops images given their bounding boxes
def crop_bounding_box(image, bounding_boxes):

    cropped_images = list()
    
    for i in range(0, len(bounding_boxes)):
        x, y, w, h = bounding_boxes[i]
        cropped_image = image[(y-10):(y+h+10), (x-10):(x+w+10)]
        cropped_images.append(cropped_image)
    
    return cropped_images

# define a function that will resize images to predetermined standard size for model 
# prediction (which is 150x150 in our case)
def resize_images(images_list, pixels_height = 150, pixels_width = 150):
    
    resized_imgs = []
    
    for image in images_list:
        try:
            resized_image = cv.resize(image, (pixels_height, pixels_width))
            resized_imgs.append(resized_image)
        except:
            break
            
    return resized_imgs

# retrieve keys from dictionary based on values
def get_classes(labels, my_dict):
    keys_list = []
    for label in labels:
        for key, value in my_dict.items():
             if label == value:
                    keys_list.append(key)

    return keys_list

# preprocess predicted labels and prepare for calculating
def preprocess_equation(digits_and_symbols):
    
    if len(digits_and_symbols) <= 3:
        return digits_and_symbols
    else:
        # join all elements of list into one string
        join = ''.join(digits_and_symbols)
        
        # separate previously joined string with separators according to regex [^.0-9] (matches all characters except 
        # decimal point and numbers)
        equation_as_list = re.split('([^.0-9])', join)
        
        return equation_as_list

# mathematical operations
def solve_equation(equation_as_list):
    
    result = None
    
    if len(equation_as_list) == 1:
        result = float(equation_as_list[0])
        
    if len(equation_as_list) == 2:
        result = float(equation_as_list[0])**float(equation_as_list[1])
    
    # check if equation has 3 members (in that case middle members always has to be operator) 
    # if this is true, simply do the operation
    if len(equation_as_list) == 3:
        # check if this equation is multiplication
        if equation_as_list[1] == '*':
            result = float(equation_as_list[0]) * float(equation_as_list[2])
        # check if this equation is division
        if equation_as_list[1] == '/':
            result = float(equation_as_list[0]) / float(equation_as_list[2])
        # check if this equation is addition
        if equation_as_list[1] == '+':
            result = float(equation_as_list[0]) + float(equation_as_list[2])
        # check if this equation is subtraction
        if equation_as_list[1] == '-':
            result = float(equation_as_list[0]) - float(equation_as_list[2])
    
    return result

def equation_image_preprocess_pipeline(img):
    # find all conours in a given picture
    contours, hierarchy = find_contours(img)
    
    # create list of bounding boxes (list of tuples)
    boundingBoxes = [cv.boundingRect(contour) for contour in contours]
    
    # sort list of bounding boxes by first element of tuples (which is x coordinate) 
    boundingBoxes.sort()
    
    # drop first element (bounding box that frames whole image)
    boundingBoxes = boundingBoxes[1:]
    
    # remove overlapping bounding boxes
    boundingBoxes_filtered = remove_overlapping_bounding_boxes(boundingBoxes)
    
    # crop images given their bounding boxes
    cropped_imgs = crop_bounding_box(img, boundingBoxes_filtered)
    
    # resize images to right size for prediction
    resized_imgs = resize_images(cropped_imgs)

    # create an numpy array of resized images
    resized_imgs_array = np.array(resized_imgs)

    return resized_imgs_array

# pipeline for prediction and calculation
def predict_and_calc_pipeline(images_array):
    load_saved_artifacts()
    
    # make predictions
    predictions = __model.predict(images_array)
    
    # get predicted labels from model predictions
    predicted_labels = [np.argmax(i) for i in predictions]
    
    # get classes from predicted labels
    digits_and_symbols = get_classes(predicted_labels, __class_name_to_number)
    
    # preprocessing of a list of single digits and mathematical symbols
    equation_as_list = preprocess_equation(digits_and_symbols)
    
    # get solution of a mathematical equation from image
    solution = solve_equation(equation_as_list)
    
    return solution


def main_pipeline(img):
    imgs_array = equation_image_preprocess_pipeline(img)
    solution = predict_and_calc_pipeline(imgs_array)
    
    return solution

if __name__ == '__main__':
    load_saved_artifacts()
    main_pipeline()

