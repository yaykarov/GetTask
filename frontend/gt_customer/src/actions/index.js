import Axios from 'axios';
import { BACKEND_URL } from '../utils/constants';
import { getToken } from '../utils';

export function logout() {
    return {
        type: 'LOG_OUT',
    };
}

export function setFilter(filterStatus) {
    return {
        type: 'UPDATE_REQUESTS_FILTER',
        payload: { filterStatus },
    };
}

export function setSorting(sorting) {
    return {
        type: 'UPDATE_REQUESTS_SORTING',
        payload: { sorting },
    };
}

const defaultAxiosConfig = {
    responseType: 'json',
    method: 'GET',
};

const requestCounters = [];

export function fetch(reducer, url, config = {}) {
    return (params, data = {}) => {
        requestCounters[reducer] = (requestCounters[reducer] || 0) + 1;
        const _requestID = requestCounters[reducer];

        return (dispatch) => {
            dispatch(fetchRequest(reducer));
            return new Promise((resolve, reject) => {
                Axios({
                    ...defaultAxiosConfig,
                    ...config,
                    url: `${BACKEND_URL}${url}`,
                    params,
                    data,
                    headers: { Authorization: `Bearer ${getToken()}` },
                }).then(
                    (data) => {
                        if (requestCounters[reducer] === _requestID && getToken()) {
                            dispatch(fetchSuccess(data, reducer));
                        }
                        resolve({ payload: data });
                    },
                    (error) => {
                        const response = error.response;
                        if (response) {
                            const error_code = response.status;
                            if (error_code === 403 || error_code === 401) dispatch(logout());
                        }
                        dispatch(fetchFailure(error, reducer));
                        reject({ error });
                    }
                );
            });
        };
    };
}

function fetchRequest(reducer) {
    return {
        type: `${reducer}_REQUEST`,
    };
}
function fetchSuccess(data, reducer) {
    return {
        type: `${reducer}_SUCCESS`,
        payload: data,
    };
}
function fetchFailure(data, reducer) {
    return {
        type: `${reducer}_FAILURE`,
        error: data,
    };
}

export function setSelectedMapRequestId(id) {
    return (dispatch) => {
        dispatch({ type: 'SET_SELECTED_MAP_REQUEST', id: id });
    };
}

export function setSelectedMapRequestType(request_type) {
    return (dispatch) => {
        dispatch({ type: 'SET_SELECTED_MAP_REQUEST_TYPE', request_type: request_type });
    };
}

//Работа с неавторизованными пользователями
export const obtainToken = fetch('OBTAIN_TOKEN', 'gt/customer/obtain_token/', { method: 'POST' });
export const signup = fetch('SIGNUP', 'gt/customer/signup/', { method: 'POST' });
export const resetPassword = fetch('RESET_PASSWORD', 'gt/customer/reset_password/', {
    method: 'POST',
});
export const updatePassword = fetch('UPDATE_PASSWORD', 'gt/customer/update_password/', {
    method: 'POST',
});
export const finishRegistration = fetch(
    'FINISH_REGISTRATION',
    'gt/customer/finish_registration/',
    { method: 'POST' }
);
//Информация об аккаунте
export const accountInfo = fetch('ACCOUNT_INFO', 'gt/customer/account_info/');
//Данные заявок
export const fetchRequests = fetch('FETCH_REQUESTS', 'gt/customer/v2/delivery/request/');
export const fetchRequestsOnMap = fetch(
    'FETCH_REQUESTS_ON_MAP',
    'gt/customer/v2/delivery/map/request/'
);
export const fetchRequestsOnMapAutocomplete = fetch(
    'FETCH_REQUESTS_ON_MAP_AUTOCOMPLETE',
    'gt/customer/v2/delivery/map/autocomplete/request/'
);
export const updateRequest = fetch('UPDATE_REQUEST', 'gt/customer/v2/delivery/request/update/', {
    method: 'POST',
});
export const updateAdressRequest = fetch(
    'UPDATE_REQUEST',
    'gt/customer/v2/delivery/request/item/update/',
    {
        method: 'POST',
    }
);
export const cancelRequest = fetch('CANCEL_REQUEST', 'gt/customer/cancel_request/', {
    method: 'POST',
});
export const removeRequest = fetch('REMOVE_REQUEST', 'gt/customer/remove_request/', {
    method: 'POST',
});
export const createRequest = fetch('CREATE_REQUEST', 'gt/customer/v2/delivery/request/create/', {
    method: 'POST',
});
export const addAddressToRequest = fetch(
    'CREATE_REQUEST',
    'gt/customer/v2/delivery/request/item/create/',
    {
        method: 'POST',
    }
);

export const moveItem = fetch('MOVE_ITEM', 'gt/customer/move_item/', { method: 'POST' });
export const removeItem = fetch('REMOVE_ITEM', 'gt/customer/remove_item/', { method: 'POST' });
export const copyItem = fetch('COPY_ITEM', 'gt/customer/copy_item/', { method: 'POST' });
export const fetchLocation = fetch('FETCH_LOCATIONS', 'gt/customer/location_autocomplete/');
//Данные импорта заявок
export const fetchImports = fetch('FETCH_IMPORTS', 'gt/customer/imports/');
//Данные о выставленных счетах
export const fetchInvoices = fetch('FETCH_INVOICES', 'gt/customer/invoices/');
//Данные о сверках
export const fetchReports = fetch('FETCH_REPORTS', 'gt/customer/reports/');
export const confirmReport = fetch('CONFIRM_REPORT', 'gt/customer/confirm_report/', {
    method: 'POST',
});
//Информация и редактирование организации
export const fetchOrganization = fetch('FETCH_ORGANIZATION', 'gt/customer/legal_entity_info/');
export const updateOrganization = fetch(
    'UPDATE_ORGANIZATION',
    'gt/customer/update_legal_entity_info/',
    {
        method: 'POST',
    }
);
//Данные о контактах
export const fetchContacts = fetch('FETCH_CONTACTS', 'gt/customer/contact_persons/');
export const updateContacts = fetch('UPDATE_CONTACTS', 'gt/customer/update_contact_person/', {
    method: 'POST',
});
export const addContact = fetch('ADD_CONTACT', 'gt/customer/add_contact_person/', {
    method: 'POST',
});
//Данные об адресе
export const updateAddressOptions = fetch(
    'UPDATE_ADDRESS_OPTIONS',
    'gt/customer/item_autocomplete/'
);
