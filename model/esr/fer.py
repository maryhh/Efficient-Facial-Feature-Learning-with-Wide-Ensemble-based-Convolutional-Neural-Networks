#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
TODO: Write docstring
"""

__author__ = "Henrique Siqueira"
__email__ = "siqueira.hc@outlook.com"
__license__ = "MIT license"
__version__ = "0.1"


class FER:
    """
    This class implements the facial expression recognition object that contains the elements
    to be displayed on the screen such as an input image and ESR-9's outputs.
    """

    # TODO: Implement Grad-CAM
    def __init__(self, image=None, face_image=None, face_coordinates=None, list_emotion=None, list_affect=None):
        """
        Initialize FER object.
        :param image: (ndarray) input image.
        """
        self.input_image = image

        self.face_coordinates = face_coordinates
        self.face_image = face_image
        self.list_emotion = list_emotion
        self.list_affect = list_affect
        self._list_grad_cam = None

    def get_grad_cam(self, i):
        if self._list_grad_cam is None:
            return None
        else:
            return self._list_grad_cam[i]
