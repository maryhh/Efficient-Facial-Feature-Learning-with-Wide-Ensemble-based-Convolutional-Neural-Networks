#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
This module implements computer vision methods.
"""

__author__ = "Henrique Siqueira"
__email__ = "siqueira.hc@outlook.com"
__license__ = "MIT license"
__version__ = "0.1"

# External Libraries
import numpy as np
import torch
from torchvision import transforms
from PIL import Image
import cv2
import dlib

# Modules
from model.esr.fer import FER
from model.utils import uimage, udata
from model.esr.esr_9 import Ensemble


# Haar cascade parameters
_HAAR_SCALE_FACTOR = 1.2
_HAAR_NEIGHBORS = 9
_HAAR_MIN_SIZE = (60, 60)

# Haar cascade parameters
_DLIB_SCALE_FACTOR_SMALL_IMAGES = [0.5, 1.0]
_DLIB_SCALE_FACTOR_LARGE_IMAGES = [0.2, 0.5]
_DLIB_SCALE_FACTOR_THRESHOLD = (500 * 500)

# Face detector methods
_ID_FACE_DETECTOR_DLIB = 1
_ID_FACE_DETECTOR_DLIB_STANDARD = 2
_FACE_DETECTOR_DLIB = None

_ID_FACE_DETECTOR_HAAR_CASCADE = 3
_FACE_DETECTOR_HAAR_CASCADE = None

# Facial expression recognition network: ensemble with shared representations (ESR)
_ESR_9 = None


# Public methods >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>

def detect_face(image, face_detection_method=_ID_FACE_DETECTOR_DLIB):
    """
    Detects faces in an image.

    :param image: (ndarray) Raw input image.
    :param face_detection_method: (int) (1) haar cascade classifiers or (2) Dlib face detection method.
    :return: (list) Tuples with coordinates of a detected face.
    """

    face_coordinates = []

    # Converts to greyscale
    greyscale_image = uimage.convert_bgr_to_grey(image)

    if face_detection_method == _ID_FACE_DETECTOR_HAAR_CASCADE:
        face_coordinates = _haar_cascade_face_detection(greyscale_image, _HAAR_SCALE_FACTOR, _HAAR_NEIGHBORS, _HAAR_MIN_SIZE)
    elif face_detection_method == _ID_FACE_DETECTOR_DLIB:
        # If input image is large, upper-bound of the scale factor is 0.5
        scale_factors = _DLIB_SCALE_FACTOR_LARGE_IMAGES if (greyscale_image.size > _DLIB_SCALE_FACTOR_THRESHOLD) else _DLIB_SCALE_FACTOR_SMALL_IMAGES

        # Down-sample the image to speed-up face detection
        for scale in scale_factors:
            greyscale_image_re_scaled = uimage.resize(greyscale_image, f=scale)
            face_coordinates = _dlib_face_detection(greyscale_image_re_scaled)

            # If found a face, then stop iterating
            if len(face_coordinates) > 0:
                face_coordinates = ((1 / scale) * face_coordinates).astype(int)
                break
    else: # Standard Dlib
        face_coordinates = _dlib_face_detection(greyscale_image).astype(int)

    # Returns None if no face is detected
    return face_coordinates[0] if (len(face_coordinates) > 0 and (np.sum(face_coordinates[0]) > 0)) else None


def recognize_facial_expression(image, on_gpu, face_detection_method):
    """
    Detects a face in the input image.
    If more than one face is detected, the biggest one is used.
    Afterwards, the detected face is fed to ESR-9 for facial expression recognition.
    The face detection phase relies on third-party methods and ESR-9 does not verify
    if a face is used as input or not (false-positive cases).

    :param on_gpu:
    :param image: (ndarray) input image.
    :return: An FER object with the components necessary for display.
    """

    to_return_fer = None

    # Detect face
    face_coordinates = detect_face(image, face_detection_method)

    if face_coordinates is None:
        to_return_fer = FER(image)
    else:
        face = image[face_coordinates[0][1]:face_coordinates[1][1], face_coordinates[0][0]:face_coordinates[1][0], :]

        # Get device
        device = torch.device("cuda" if on_gpu else "cpu")

        # Pre_process detected face
        input_face = _pre_process_input_image(face)
        input_face = input_face.to(device)

        # Recognize facial expression
        emotion, affect = _predict(input_face, device)

        # Initialize GUI object
        to_return_fer = FER(image, face, face_coordinates, emotion, affect)

    return to_return_fer

# Public methods <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<


# Private methods >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>

def _dlib_face_detection(image):
    """
    Face detection using the CNN implementation from Dlib.

    References:
    Davis E. King. Dlib-ml: A Machine Learning Toolkit. Journal of Machine Learning Research 10, pp. 1755-1758, 2009

    :param image: (ndarray) Raw image
    :return: (ndarray) The coordinates of the detected face
    """
    global _FACE_DETECTOR_DLIB

    face_coordinates = []

    # Verifies if dlib is initialized
    if _FACE_DETECTOR_DLIB is None:
        _FACE_DETECTOR_DLIB = dlib.cnn_face_detection_model_v1('./model/utils/templates/dlib/cnn_face_detector.dat')

    # Calls dlib's face detection method
    faces = _FACE_DETECTOR_DLIB(image)

    # Gets coordinates
    if not (faces is None):
        for face_id, net_output in enumerate(faces):
            xi, xf, yi, yf = (net_output.rect.left(), net_output.rect.right(), net_output.rect.top(), net_output.rect.bottom())
            face_coordinates.append([[xi, yi], [xf, yf]])

    return np.array(face_coordinates)


def _haar_cascade_face_detection(image, scale_factor, neighbors, min_size):
    """
    Face detection using the Haar Feature-based Cascade Classifiers (Viola and Jones, 2004).

    References:
    Viola, P. and Jones, M. J. (2004). Robust real-time face detection. International journal of computer vision, 57(2), 137-154.

    :param image: (ndarray) Raw image.
    :param scale_factor: Scale factor to resize input image.
    :param neighbors: Minimum number of bounding boxes to be classified as a face.
    :param min_size: Minimum size of the face bounding box.
    :return: (ndarray) Coordinates of the detected face.
    """
    global _FACE_DETECTOR_HAAR_CASCADE

    # Verifies if haar cascade classifiers are initialized
    if _FACE_DETECTOR_HAAR_CASCADE is None:
        _FACE_DETECTOR_HAAR_CASCADE = cv2.CascadeClassifier("./model/utils/templates/haar_cascade/frontal_face.xml")

    # Runs haar cascade classifiers
    faces = _FACE_DETECTOR_HAAR_CASCADE.detectMultiScale(image, scale_factor, neighbors, minSize=min_size)

    # Gets coordinates
    face_coordinates = [[[x, y], [x + w, y + h]] for (x, y, w, h) in faces] if not (faces is None) else []

    return np.array(face_coordinates)


def _pre_process_input_image(image):
    """
    Pre-processes an image for ESR-9.

    :param image: (ndarray)
    :return: (ndarray) image
    """

    image = uimage.resize(image, Ensemble.INPUT_IMAGE_SIZE)
    image = Image.fromarray(image)
    image = transforms.Normalize(mean=Ensemble.INPUT_IMAGE_NORMALIZATION_MEAN,
                                 std=Ensemble.INPUT_IMAGE_NORMALIZATION_STD)(transforms.ToTensor()(image)).unsqueeze(0)

    return image


def _predict(input_face, device):
    global _ESR_9

    if _ESR_9 is None:
        _ESR_9 = Ensemble.load(device)

    to_return_emotion = []
    to_return_affect = None

    # Recognizes facial expression
    emotion, affect = _ESR_9(input_face)

    # Computes ensemble prediction for affect
    # Converts from Tensor to ndarray
    affect = np.array([a[0].cpu().detach().numpy() for a in affect])
    # Normalizes arousal
    affect[:, 1] = np.clip((affect[:, 1] + 1)/2.0, 0, 1)
    # Computes mean arousal and valence as the ensemble prediction
    ensemble_affect = np.expand_dims(np.mean(affect, 0), axis=0)
    # Concatenates the ensemble prediction to the list of affect predictions
    to_return_affect = np.concatenate((affect, ensemble_affect), axis=0)

    # Computes ensemble prediction for emotion
    # Converts from Tensor to ndarray
    emotion = np.array([e[0].cpu().detach().numpy() for e in emotion])
    # Gets number of classes
    num_classes = emotion.shape[1]
    # Computes votes and add label to the list of emotions
    emotion_votes = np.zeros(num_classes)
    for e in emotion:
        e_idx = np.argmax(e)
        to_return_emotion.append(udata.AffectNetCategorical.get_class(e_idx))
        emotion_votes[e_idx] += 1

    # Concatenates the ensemble prediction to the list of emotion predictions
    to_return_emotion.append(udata.AffectNetCategorical.get_class(np.argmax(emotion_votes)))

    return to_return_emotion, to_return_affect

# Private methods <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
