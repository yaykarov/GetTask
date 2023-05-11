import matplotlib.pyplot as ppl
# import numpy as np


def show_plot(image):
    fig, ax = ppl.subplots()
    ax.imshow(image)
    ppl.show()


def get_digit_pic(image, xfrom=0, xsize=40, median=0.6):
    xmin = -1
    xmax = -1
    # print("(shape: {0})".format(image.shape[1]))
    for i in range(xfrom, xfrom + xsize):
        if i >= image.shape[1]:
            break
        if max(image[:, i]) > median and xmin == -1:
            xmin = i
        if max(image[:, i]) <= median and xmin != -1:
            xmax = i
            break
    # print("({0},{1})".format(xmin,xmax))
    if xmin == -1 or xmax == -1:
        return (-1, -1), (-1, -1)
    ymin = -1
    ymax = -1
    for i in range(0, image.shape[0]):
        if max(image[i, xmin:xmax]) > median and ymin == -1:
            ymin = i
        if max(image[i, xmin:xmax]) < median and ymin != -1:
            ymax = i
            break
    # print("({0},{1})".format(ymin,ymax))
    return (xmin, xmax), (ymin, ymax)


def show_digits(image, ncols=15):
    fig, axes = ppl.subplots(ncols=ncols)
    xmax = 0
    for i in range(0, ncols):
        # print(xmax)
        (xmin, xmax), (ymin, ymax) = get_digit_pic(image, xfrom=xmax)
        if xmin == -1 or xmax <= 0 or ymin == -1 or ymax <= 0:
            break
        axes[i].set_title("({0},{1})".format(xmin, xmax))
        axes[i].imshow(image[ymin:ymax, xmin:xmax])

    ppl.show()


def get_corell(image1, image2, median=0.4):
    m = 0
    xsize = image1.shape[0]
    ysize = image1.shape[1]
    xscale = image2.shape[0] / image1.shape[0]
    yscale = image2.shape[1] / image1.shape[1]
    # print("{0} - {1}".format(image1.shape,image2.shape))
    # print("{0},{1}".format(xscale,yscale))
    n = xsize * ysize
    for x in range(0, xsize):
        img2x = round(min(image2.shape[0] - 1, x * xscale))
        for y in range(0, ysize):
            img2y = round(min(image2.shape[1] - 1, y * yscale))
            if image1[x, y] > median and image2[img2x, img2y] > median or image1[x, y] < median and\
                    image2[img2x, img2y] < median:
                m += 1
    return m / n


def recognize_digit_avito(image, tol=0.6, exact_val_acc=0.95):
    url1 = "data:image/png;base64,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"
    url2 = "data:image/png;base64,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"
    image1main = ppl.imread(fname=url1)[:, :, 3]
    image1y = (13, 44)
    max_acc_digit = 0
    max_acc_value = 0
    image1x = {0: (64, 84), 1: (126, 137), 2: (146, 167), 3: (208, 228), 6: (268, 289), 7: (293, 313), 8: (5, 25),
               9: (40, 60)}

    for digit in image1x.keys():
        # print("digit: {0}->{1}".format(digit,image1x[digit]))
        digit_image = image1main[image1y[0]:image1y[1], image1x[digit][0]:image1x[digit][1]]
        acc = get_corell(image, digit_image)
        if acc > exact_val_acc:
            return digit
        if acc > max_acc_value:
            max_acc_digit = digit
            max_acc_value = acc
    image2main = ppl.imread(fname=url2)[:, :, 3]
    image2y = (13, 44)
    image2x = {4: (122, 143), 5: (64, 84)}
    for digit in image2x.keys():
        # print("digit: {0}->{1}".format(digit,image2x[digit]))
        digit_image = image2main[image2y[0]:image2y[1], image2x[digit][0]:image2x[digit][1]]
        acc = get_corell(image, digit_image)
        if acc > exact_val_acc:
            return digit
        if acc > max_acc_value:
            max_acc_digit = digit
            max_acc_value = acc
    # print("accuracy: {}".format(max_acc_value))
    if max_acc_value < tol:
        return -1
    else:
        return max_acc_digit


def recognize_digit_birge(image, tol=0.6, exact_val_acc=0.95):
    url1 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAHgAAAASCAYAAACQCxruAAAACXBIWXMAAA7EAAAOxAGVKw4bAAADiUlEQVRoge3ZT6hVVRQG8J8PFUt7BNo/ipKIIHuYRUiU9GeVhShYNEhEKCkSs5KQrAYiESLqQBqJTiQjgiAiEIWgVYQ1SZsUYiVmDkLQ0MTUTJ4N9r55eTzvvQ5eeR/3gzO4Z+9vrbXXOnt9+5w75vz583oYvej7vwPoYWTRK/AoR9cXOCKujohp3cT9LzGmocERMQsbMANnkViemYci4iZsRuAkPsKKzDzTAXcjXsVgk98dmTk/IqbiXTyMsdiFpZl5oNqdgY2YWflf4ZXMPFCT+y2urDYnZuap4RYZEVvxXGNOO26ruC7F7+WAPoiIfuzEl5iMOzAen9Z5O3Gijt2Fe5UEdMKdim2ZOa7pmh8RY/E5DuJG3IBT+LjanVTHv8E1dc5xfAKZuTczJ+KBVguMiAexsPleK267uDr1e7mg0aJvwyRsyMxTmfmbsnOmR8R0DOD1prF1WNABt08p8M/D+J6KQ1idmScz8wQ2YUZN8qTq5+1q9wS2Ntlti4gYr3SeLZ2npG1cXYVGwHuVJ3ZFRKxR2s9SbG+a25zUw+iPiAmtuJk5WNvd0xHxWvW3A8sycz8eGRLPbOzKzHPVx/rGQPX1DD7LzEGd4U38hA/xcieEDuLqKvRB1dKnlCT8iSOYhmfxg1LAVRExISKmKAWEvlbcWpSDSju/DncqO37r0EAiYqGik4uH3J8XEadxGk9iWScLi4jba5xLOpnfws6wcXULGho8XtGYLZio6M5+vFd3yxyldR3BHkUL4Vwb7pnMvDszt2XmYG3f72Bec5uNiBeUh2BO3UH/IjO3Z+YV1fZ2fNDh2jbjrcw8fCkJaUaruLoFjSQP4FasrXp3WNHReRHRl5n7MnN2Zl6VmbcoRT6amWfbcG+OiA11Jw+LiFiJNXg0M3c33b82Il6qD5B6Un0fM9tpcETcg1nYVHf/F3Xo94hYcHFm+7i6DQ0NPqCcFJdHxFrlgLME+6qO9mN8Zh6NiAGsduHgclGustNfxJmqz/14wwV9XodFeCgz9w2J7axyyJoSEesVbX8eu9tpcGZ+h3GN3xFxP77G5E5eadrE1VVoaPBxzMXjOIZflELNr/MGsCci/lJeibZhVTtuPYHOxWP4Az8qJ9TFEXEfVuJ6fB8Rfzddi6rdJ+p1DL9igqL3I4Z2cY2k75HAmN6fDaMbXf+psofW6BV4lKNX4FGOXoFHOf4BJTrUbgTBlYAAAAAASUVORK5CYII="
    url2 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAHgAAAASCAYAAACQCxruAAAACXBIWXMAAA7EAAAOxAGVKw4bAAADvUlEQVRoge3YS4jVVRwH8M8MIZYholYWEvbAwFwkVItq068HiYFIBNmmB9UghYO4qI1ERIjMYgiCqIQhN70oC8KK5BcEtSjcDWJvkxJJIxPTSURb/M/Vf3fm3r9COtNwv5t77znn9z6/x7l9J0+e1MP0Rf9kK9DDuUUvwNMcvQCfI0TEnIhYMtl69DX14Ih4DC+3LfejPzP7ypmFeAWBw3gb6zNzrMbnGazBAvyImzLzcETchiHcgGNIDGbmnkJ3RY33GN7DIB5s0quTXDxwBjYNYy1O1M5sy8yV3ewtQf0aFxWaWZl5ZALXnhdc0L4QEbfgC0WxzNyMzW1n3sLe2tJHGMU8zMFWvIiBcn4I92JFZo5GxOIS3NmF9iXcUWhfwwdYVnhvLbwvwcXl93BmDjTp1UluoWuyaRG2ZOYjE/ito72ZuROzan6cVIwLcBNKRi/E6vJ7KZZiebmpRyJiE0YwUIK4tuyPQmZ+W9hdqwraUI12GJ9ERD+uxM24v7Y/hNeVy9NFr25yu9pUsAjvTHC2q73NHjy/OKsAR8RcbMStmdkqXf1tn7APsyNiJhZjBpZHxAjmYjsex07sxvqIeEFV1tbgw8w8ERELCr8DNd6/tXi3WkAHvTrKzcxT/DrQUgX4vohYV/y0DU822VtvS1MBp5SMiKMRcRSflaXfa2stDGJ7WyaMqoK0ISJmRsR8VZBa/GeU77/iOlyF+RgpzliFp/AX9mMJHmrXr5vuHfTqKLeNzzjacjF3q8ruZbheVW1GzsDeKYVTCmXmhZl5IW4vS/Nqay08ijfqDMqtX6668fuxAwfL9nGnh5TNmTlWsmcT7imOfBevYhYux/eqEsy/B5x21PfG6dUgt78bbTm/LDO3ZOaJzNyL51X9XIO9UwpnXKJL71mIz9v3MnMX7qqdfRgHMvNYROwpy4tUt58qu46rsvVqbGzrwZ+WIOwr5y9VZU3r+6Faee6kV0e5rVLcibZMyYPYMFHJ7WZv+9nJxtn04BvxS2YebN8oA82MzDxQnPasKitl5t6I+BjDEbFalVnr8b7q2XIEgxGxUTVwDWBXCcLuiPgKz0XEGlWPXoc3m/RqkNtk0yE8gbEyG8zG007PBh3tnWoY1zMy88vM7Jvg7XaN01nUjqXYERF/q54QW7Chtr9a9QT5AT+rsmugOHYF7sYf+EkV5JU12lWqAWk/vlOV8HVnqNeEcptoM/NQ0etO/IlvCm3rydRk75RB4x8dPfy/MeWmvh7+W/QCPM3RC/A0Ry/A0xz/ADVY64waqhAUAAAAAElFTkSuQmCC"
    image1main = ppl.imread(fname=url1)[:, :, 3]
    image1y = (4, 13)
    max_acc_digit = 0
    max_acc_value = 0
    image1x = {1: (47, 50), 2: (31, 37), 3: (39, 45), 4: (54, 60), 5: (24, 30), 8: (2, 8), 9: (9, 15)}

    for digit in image1x.keys():
        # print("digit: {0}->{1}".format(digit,image1x[digit]))
        digit_image = image1main[image1y[0]:image1y[1], image1x[digit][0]:image1x[digit][1]]
        acc = get_corell(image, digit_image)
        if acc > exact_val_acc:
            return digit
        if acc > max_acc_value:
            max_acc_digit = digit
            max_acc_value = acc
    image2main = ppl.imread(fname=url2)[:, :, 3]
    image2y = (4, 13)
    image2x = {0: (40, 46), 6: (25, 31), 7: (47, 53)}
    for digit in image2x.keys():
        # print("digit: {0}->{1}".format(digit,image2x[digit]))
        digit_image = image2main[image2y[0]:image2y[1], image2x[digit][0]:image2x[digit][1]]
        acc = get_corell(image, digit_image)
        if acc > exact_val_acc:
            return digit
        if acc > max_acc_value:
            max_acc_digit = digit
            max_acc_value = acc
    # print("accuracy: {}".format(max_acc_value))
    if max_acc_value < tol:
        return -1
    else:
        return max_acc_digit


def get_digits(fname, channel=3, site="avito"):
    image = ppl.imread(fname=fname)[:, :, channel]
    offset = 0
    result = 0
    # print("image shape: {}".format(image.shape))
    while offset + 5 < image.shape[1]:
        # print("offset: {}".format(offset))
        (xmin, xmax), (ymin, ymax) = get_digit_pic(image, xfrom=offset)
        if xmin == -1 or xmax <= 0 or ymin == -1 or ymax <= -1:
            break
        if site == "avito":
            digit = recognize_digit_avito(image[ymin:ymax, xmin:xmax])
        else:
            digit = recognize_digit_birge(image[ymin:ymax, xmin:xmax])
        # print("digit {0}".format(digit))
        if digit != -1:
            result = result * 10 + digit
        offset = xmax
    return int(str(result)[1:])
