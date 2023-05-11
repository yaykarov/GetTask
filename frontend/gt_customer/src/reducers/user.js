import { getToken, removeToken } from '../utils';

const user = (
    state = { info: { name: null, balance: null }, token: null, isLoading: false, error: null },
    action
) => {
    switch (action.type) {
        case 'OBTAIN_TOKEN_REQUEST':
            return { ...state, isLoading: true };
        case 'OBTAIN_TOKEN_SUCCESS':
            return { ...state, isLoading: false, token: action.payload.data.access_token };
        case 'OBTAIN_TOKEN_FAILURE':
            return { ...state, isLoading: false, error: action.error.response.data.message };

        case 'FINISH_REGISTRATION_REQUEST':
            return { ...state, isLoading: true };
        case 'FINISH_REGISTRATION_SUCCESS':
            return { ...state, isLoading: false, token: action.payload.data.access_token };
        case 'FINISH_REGISTRATION_FAILURE':
            return { ...state, isLoading: false, error: action.error.response.data.message };

        case 'ACCOUNT_INFO_REQUEST':
            return { ...state, isLoading: false };
        case 'ACCOUNT_INFO_SUCCESS':
            return {
                ...state,
                token: getToken(),
                isLoading: false,
                info: {
                    ...action.payload.data,
                    name: action.payload.data.full_name,
                    balance: action.payload.data.balance,
                    registrationStatus: action.payload.data.registration_status,
                    importsUpdated: action.payload.data.imports_updated,
                },
            };
        case 'ACCOUNT_INFO_FAILURE':
            return { ...state, isLoading: false, error: action.error.response.data.message };

        case 'LOG_OUT':
            removeToken();
            return { ...state, token: null };

        default:
            return state;
    }
};

export default user;
