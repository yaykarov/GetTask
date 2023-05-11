import os
import time


def remove_old_files(path, day):
    if os.path.exists(path):
        for f in os.listdir(path):
            if os.stat(
                    os.path.join(path, f)
            ).st_mtime < time.time() - day * 86400:
                if os.path.isfile(os.path.join(path, f)):
                    os.remove(os.path.join(path, f))
    else:
        os.makedirs(path)


def get_unique_path(path):
    i = 0
    unique_path = path
    while os.path.exists(unique_path):
        unique_path = '{}_{}'.format(path, i)
    return unique_path


def jpeg_to_jpg(filename):
    if filename.endswith('jpeg'):
        return filename[:-4] + 'jpg'
    return filename
