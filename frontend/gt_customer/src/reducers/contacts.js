const contacts = (state = { list: [], isLoading: false, error: null }, action) => {
    switch (action.type) {
        case 'FETCH_CONTACTS_REQUEST':
            return { ...state, isLoading: true };
        case 'FETCH_CONTACTS_SUCCESS':
            return { ...state, isLoading: false, list: action.payload.data };
        case 'FETCH_CONTACTS_FAILURE':
            return { ...state, isLoading: false, error: action.error.response.message };

        default:
            return state;
    }
};

export default contacts;
