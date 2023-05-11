import cv2 as cv
import numpy


def _read(filename):
    img = cv.imread(filename)
    return img, img.shape[0], img.shape[1]


COLOR = (195, 195, 195)

TITLE_TMPL, TITLE_TMPL_H, TITLE_TMPL_W = _read('utils/img_templates/title.png')

TITLE_W = 100
TITLE_OFFSET = 85


def _hide_title(img):
    m = cv.matchTemplate(img, TITLE_TMPL, cv.TM_SQDIFF_NORMED)

    m_w = m.shape[1]
    best_match = numpy.argmin(m)

    t_y = int(best_match / m_w)
    t_x = best_match % m_w

    x = t_x + TITLE_OFFSET + TITLE_TMPL_W

    cv.rectangle(
        img,
        (x, t_y),
        (x + TITLE_W, t_y + TITLE_TMPL_H),
        COLOR,
        -1
    )


SUM1_TMPL, SUM1_TMPL_H, SUM1_TMPL_W = _read('utils/img_templates/sum1.png')

SUM1_W = 100
SUM1_H = 50
SUM1_Y_OFFSET = 8


def _hide_sum1(img):
    m = cv.matchTemplate(img, SUM1_TMPL, cv.TM_SQDIFF_NORMED)

    m_w = m.shape[1]
    best_match = numpy.argmin(m)

    t_y = int(best_match / m_w)
    t_x = best_match % m_w

    x = t_x + SUM1_TMPL_W - SUM1_W
    y = t_y + SUM1_TMPL_H + SUM1_Y_OFFSET

    cv.rectangle(
        img,
        (x, y),
        (x + SUM1_W, y + SUM1_H),
        COLOR,
        -1
    )


SUM2_TMPL, SUM2_TMPL_H, SUM2_TMPL_W = _read('utils/img_templates/sum2.png')

SUM2_W = 110
SUM2_X_OFFSET = 88


def _hide_sum2(img):
    m = cv.matchTemplate(img, SUM2_TMPL, cv.TM_SQDIFF_NORMED)

    m_w = m.shape[1]
    best_match = numpy.argmin(m)

    t_y = int(best_match / m_w)
    t_x = best_match % m_w

    x = t_x + SUM2_TMPL_W + SUM2_X_OFFSET

    cv.rectangle(
        img,
        (x, t_y),
        (x + SUM2_W, t_y + SUM2_TMPL_H),
        COLOR,
        -1
    )


CODE_TMPL, CODE_TMPL_H, CODE_TMPL_W = _read('utils/img_templates/qr_code.png')

CODE_H = 100
CODE_W = 100

def _hide_qr_code(img):
    m = cv.matchTemplate(img, CODE_TMPL, cv.TM_SQDIFF)

    m_w = m.shape[1]
    best_matches = numpy.argsort(m, axis=None)[:3]

    t_y_min = int(best_matches[0] / m_w)
    t_x_min = best_matches[0] % m_w

    for best_match in best_matches[1:]:
        t_y = int(best_match / m_w)
        t_x = best_match % m_w

        if t_y <= t_y_min and t_x <= t_x_min:
            t_y_min, t_x_min = t_y, t_x

    cv.rectangle(
        img,
        (t_x_min, t_y_min),
        (t_x_min + CODE_W, t_y_min + CODE_H),
        COLOR,
        -1
    )


def _hide_all(img):
    _hide_title(img)
    _hide_sum1(img)
    _hide_sum2(img)
    _hide_qr_code(img)


def hide_all_if_check(filename):
    img = cv.imread(filename)
    if img is None:
        return None

    # assume all images with width 330 are checks
    # and all with the different width are not
    width = img.shape[1]
    if width != 330:
        return None

    _hide_all(img)

    retval, buf = cv.imencode('.jpg', img)

    return buf
