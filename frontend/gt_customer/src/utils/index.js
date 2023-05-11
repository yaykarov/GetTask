import Cookies from 'js-cookie';

const getToken = () => {
    return Cookies.get('token') || localStorage.getItem('token');
};
const setToken = (token, rememberMe = false) => {
    if (rememberMe) {
        localStorage.setItem('token', token);
    }
    Cookies.set('token', token, { expires: 1 / 24, path: '/' });
};
const removeToken = () => {
    localStorage.removeItem('token');
    Cookies.remove('token', { path: '/' });
};

const storageService = (prefix) => {
    return (Storage = {
        set(key, data) {
            const _data = JSON.stringify(data);
            localStorage.setItem(`${prefix}_${key}`, _data);

            return data;
        },
        get(key, def) {
            const result = JSON.parse(localStorage.getItem(`${prefix}_${key}`));
            return result === null && typeof def !== 'undefined' ? def : result;
        },
        remove(key) {
            localStorage.removeItem(`${prefix}_${key}`);
        },
        clear() {
            localStorage.clear();
        },
    });
};

function deepEqual(prev, next) {
    function stringify(x) {
        return Object.prototype.toString.call(x);
    }
    if (stringify(prev) !== stringify(next)) return false;
    if (prev === next) {
        return true;
    } else {
        if (stringify(prev) === '[object Object]') {
            if (Object.keys(prev).length != Object.keys(next).length) {
                return false;
            }
            for (let propName in prev) {
                if (!next.hasOwnProperty(propName)) {
                    return false;
                }
                if (prev[propName].toString() !== next[propName].toString()) {
                    if (!deepEqual(prev[propName], next[propName])) {
                        return false;
                    }
                }
            }
        } else if (stringify(prev) === '[object Array]') {
            if (prev.length !== next.length) return false;

            for (let i of prev) {
                if (!deepEqual(prev[i], next[i])) {
                    return false;
                }
            }
        } else {
            return false;
        }
    }
    return true;
}

function formatToMoney(value) {
    return new Intl.NumberFormat('ru-RU', { style: 'currency', currency: 'RUB' })
        .format(value)
        .replace(/,(\d\d).₽/, (_, firstGroup) => {
            const defaultValue = '00';

            if (firstGroup === defaultValue) {
                return '';
            }

            return `.${firstGroup}`;
        })
        .replace(/\s/g, '\u202F');
}

function getWindowEnvValue(key) {
    if (typeof window !== 'undefined') {
        const windowEnv = window?.$$environment;
        if (windowEnv !== undefined) {
            return windowEnv[key];
        }
    }

    return undefined;
}

/**
 * @param key The name of the env variable. Should start with 'REACT_APP' prefix.
 */
function getEnvValue(key, defaultValue) {
    const processEnvValue = process.env[key];
    if (processEnvValue !== undefined) {
        return processEnvValue;
    }

    const windowEnvValue = getWindowEnvValue(key);
    if (windowEnvValue !== undefined) {
        return windowEnvValue;
    }

    return defaultValue;
}

export { getToken, setToken, removeToken, storageService, deepEqual, formatToMoney, getEnvValue };
